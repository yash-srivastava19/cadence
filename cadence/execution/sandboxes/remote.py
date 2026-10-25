"""A sandbox somewhere else, reached through a command.

The command reads one request on stdin and writes one Execution on stdout.
`ssh box cadence sandbox`, `docker run -i image cadence sandbox` and a client
for a hosted sandbox all fit, so the loop never learns which one it has.

The request carries the workspace as a tarball, because the far side has no
checkout. It is packed once per workspace and sent with every job.
"""

import base64
import io
import json
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from cadence.errors import SandboxUnreachable
from cadence.execution.sandboxes.subprocess import IGNORED, Execution, Job, Subprocess

__all__ = ["Command", "answer"]

#: Room for the transport on top of the job's own limit: an upload, a
#: container start, an ssh handshake.
OVERHEAD_SECONDS = 300


class Command:
    def __init__(self, command: str) -> None:
        self.command = shlex.split(command)
        self.where = command
        self._packed: dict[str, str] = {}

    def run(self, job: Job) -> Execution:
        request = json.dumps(
            {
                "job": job.model_dump(mode="json", exclude={"workspace"}),
                "workspace": self._pack(job.workspace) if job.workspace else None,
            }
        )
        try:
            done = subprocess.run(
                self.command,
                input=request,
                capture_output=True,
                text=True,
                timeout=job.seconds + OVERHEAD_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SandboxUnreachable(f"{self.where}: {error}") from error
        if done.returncode != 0:
            raise SandboxUnreachable(
                f"{self.where} exited {done.returncode}: {done.stderr.strip()[-500:]}"
            )
        try:
            return Execution.model_validate_json(done.stdout)
        except ValueError as error:
            raise SandboxUnreachable(
                f"{self.where} did not answer with a measurement: {error}"
            ) from error

    def _pack(self, workspace: str) -> str:
        if workspace not in self._packed:
            self._packed[workspace] = _tarball(Path(workspace))
        return self._packed[workspace]


def answer(request: str) -> str:
    """The far side: one request in, one Execution out, measured here."""
    asked = json.loads(request)
    with tempfile.TemporaryDirectory(prefix="cadence-remote-") as scratch:
        workspace = None
        if asked["workspace"] is not None:
            packed = io.BytesIO(base64.b64decode(asked["workspace"]))
            with tarfile.open(fileobj=packed, mode="r:gz") as tar:
                tar.extractall(scratch, filter="data")
            workspace = scratch
        job = Job.model_validate_json(
            json.dumps({**asked["job"], "workspace": workspace})
        )
        return Subprocess().run(job).model_dump_json()


def _tarball(workspace: Path) -> str:
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="cadence-pack-") as scratch:
        copy = Path(scratch) / "repo"
        shutil.copytree(workspace, copy, ignore=IGNORED)
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(copy, arcname=".")
    return base64.b64encode(buffer.getvalue()).decode()
