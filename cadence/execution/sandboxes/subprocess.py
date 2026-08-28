import contextlib
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from statemachine import State, StateMachine

from cadence.core.types import NonBlank
from cadence.lifecycle.entity import Entity
from cadence.lifecycle.states import SandboxRunState

__all__ = [
    "Execution",
    "Job",
    "Sandbox",
    "SandboxRun",
    "SandboxRunStateMachine",
    "Subprocess",
]

KILLED_BY_TIMEOUT = "wall clock"
# RLIMIT_AS does not kill the process; it makes the allocation fail and the
# runtime say so. Only the kernel's OOM killer sends SIGKILL.
OOM_SIGNS = ("memoryerror", "std::bad_alloc", "cannot allocate memory", "out of memory")
IGNORED = shutil.ignore_patterns(".git", "__pycache__", ".venv", "*.pyc")
GRACE_SECONDS = 0.5


class Job(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    code: NonBlank
    program: NonBlank
    command: tuple[NonBlank, ...] = Field(min_length=1)
    workspace: str | None = None
    seed: int = Field(ge=0)
    seconds: float = Field(gt=0, allow_inf_nan=False)
    memory_mb: int = Field(gt=0)
    output_kb: int = Field(gt=0, default=1024)


class Execution(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    exit_status: int
    stdout: str
    stderr: str
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    killed_by: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_status == 0 and self.killed_by is None

    @property
    def timed_out(self) -> bool:
        return self.killed_by == KILLED_BY_TIMEOUT

    @property
    def out_of_memory(self) -> bool:
        if self.killed_by is not None or self.exit_status == 0:
            return False
        if self.exit_status == -signal.SIGKILL:
            return True
        blamed = self.stderr.lower()
        return any(sign in blamed for sign in OOM_SIGNS)


class SandboxRunStateMachine(StateMachine):
    running = State(value=SandboxRunState.RUNNING, initial=True)
    reaped = State(value=SandboxRunState.REAPED, final=True)
    killed = State(value=SandboxRunState.KILLED, final=True)
    orphaned = State(value=SandboxRunState.ORPHANED)

    reap = running.to(reaped)
    orphan = running.to(orphaned)
    kill = running.to(killed) | orphaned.to(killed)


class SandboxRun(Entity, machine=SandboxRunStateMachine):
    """One process group, from spawn to whatever ended it."""

    def __init__(
        self, pgid: int | None = None, status: SandboxRunState | None = None
    ) -> None:
        self.pgid = pgid
        self.status = status or SandboxRunState.RUNNING
        self.bind()

    @property
    def may_kill(self) -> bool:
        return self._permits("kill")

    def reap(self) -> None:
        """It exited on its own and we collected it."""
        self._fire("reap")

    def orphan(self) -> None:
        """It outlived the wait. Something is still running out there."""
        self._fire("orphan")

    def kill(self) -> None:
        self._fire("kill")


@runtime_checkable
class Sandbox(Protocol):
    def run(self, job: Job) -> Execution: ...


def _limits(job: Job) -> None:
    os.setsid()
    memory = job.memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    output = job.output_kb * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (output, output))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


class Subprocess:
    def __init__(self, python: str | None = None) -> None:
        self.python = python or sys.executable

    def run(self, job: Job) -> Execution:
        run = SandboxRun()
        with tempfile.TemporaryDirectory(prefix="cadence-") as scratch:
            workspace = self._laid_out(job, Path(scratch))
            started = time.monotonic()
            process = subprocess.Popen(
                list(job.command),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workspace,
                preexec_fn=lambda: _limits(job),
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": str(workspace),
                    "PYTHONHASHSEED": str(job.seed),
                    "CADENCE_SEED": str(job.seed),
                },
            )
            run.pgid = os.getpgid(process.pid)
            try:
                stdout, stderr = process.communicate(timeout=job.seconds)
                killed_by = None
                run.reap()
            except subprocess.TimeoutExpired:
                stdout, stderr = self._reap_group(run, process)
                killed_by = KILLED_BY_TIMEOUT
            duration = (time.monotonic() - started) * 1000

        return Execution(
            exit_status=process.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_ms=duration,
            killed_by=killed_by,
        )

    def _laid_out(self, job: Job, scratch: Path) -> Path:
        if job.workspace is not None:
            shutil.copytree(job.workspace, scratch / "repo", ignore=IGNORED)
            workspace = scratch / "repo"
        else:
            workspace = scratch
        (workspace / job.program).write_text(job.code)
        return workspace

    def _reap_group(
        self, run: SandboxRun, process: subprocess.Popen
    ) -> tuple[str, str]:
        # Never a bare int default on pgid: os.killpg(0, ...) signals our own
        # process group, which is cadence and everything it has spawned.
        if run.pgid is None:
            raise RuntimeError("the sandbox has no process group to reap")
        try:
            os.killpg(run.pgid, signal.SIGTERM)
        except ProcessLookupError:
            run.orphan()
        try:
            stdout, stderr = process.communicate(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(run.pgid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        run.kill()
        return stdout, stderr
