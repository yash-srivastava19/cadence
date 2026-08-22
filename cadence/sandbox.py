import json
import os
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from statemachine import State, StateMachine

from cadence.stateful import Stateful
from cadence.states import SandboxRunState

__all__ = [
    "Job",
    "Execution",
    "Sandbox",
    "SandboxRun",
    "SandboxRunMachine",
    "Subprocess",
]

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

KILLED_BY_TIMEOUT = "wall clock"
UNSERIALIZABLE = 3
GRACE_SECONDS = 0.5


class Job(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    code: NonBlank
    entry_point: NonBlank
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
        return self.exit_status == -signal.SIGKILL and self.killed_by is None


class SandboxRunMachine(StateMachine):
    running = State(value=SandboxRunState.RUNNING, initial=True)
    reaped = State(value=SandboxRunState.REAPED, final=True)
    killed = State(value=SandboxRunState.KILLED, final=True)
    orphaned = State(value=SandboxRunState.ORPHANED)

    reap = running.to(reaped)
    orphan = running.to(orphaned)
    kill = running.to(killed) | orphaned.to(killed)


class SandboxRun(Stateful, machine=SandboxRunMachine):
    def __init__(self, pgid: int | None = None, status=None) -> None:
        self.pgid = pgid
        self.status = status
        self.bind()


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


HARNESS = """\
import json, sys
source = json.loads(sys.stdin.read())
namespace = {}
exec(source["code"], namespace)
result = namespace[source["entry_point"]](*json.loads(source["inputs"]))
try:
    encoded = json.dumps(result)
except TypeError as error:
    sys.stderr.write(str(error))
    sys.exit(UNSERIALIZABLE)
sys.stdout.write(encoded)
""".replace("UNSERIALIZABLE", str(UNSERIALIZABLE))


class Subprocess:
    def __init__(self, python: str | None = None) -> None:
        self.python = python or sys.executable

    def run(self, job: Job, inputs: str = "[]") -> Execution:
        run = SandboxRun()
        with tempfile.TemporaryDirectory(prefix="cadence-") as workspace:
            harness = Path(workspace) / "harness.py"
            harness.write_text(HARNESS)
            payload = json.dumps(
                {"code": job.code, "entry_point": job.entry_point, "inputs": inputs}
            )
            started = time.monotonic()
            process = subprocess.Popen(
                [self.python, str(harness)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=workspace,
                preexec_fn=lambda: _limits(job),
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONHASHSEED": str(job.seed),
                },
            )
            run.pgid = os.getpgid(process.pid)
            try:
                stdout, stderr = process.communicate(payload, timeout=job.seconds)
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

    def _reap_group(
        self, run: SandboxRun, process: subprocess.Popen
    ) -> tuple[str, str]:
        try:
            os.killpg(run.pgid, signal.SIGTERM)
        except ProcessLookupError:
            run.orphan()
        try:
            stdout, stderr = process.communicate(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(run.pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        run.kill()
        return stdout, stderr
