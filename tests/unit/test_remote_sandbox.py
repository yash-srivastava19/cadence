import shlex
import sys

import pytest

from cadence.errors import SandboxUnreachable
from cadence.execution.runner import TrialRunner
from cadence.execution.sandboxes.remote import Command
from cadence.execution.sandboxes.subprocess import Job, Subprocess

FAR_SIDE = shlex.join(
    [
        sys.executable,
        "-c",
        "import sys; from cadence.execution.sandboxes.remote import answer;"
        " print(answer(sys.stdin.read()))",
    ]
)


def a_job(workspace):
    (workspace / "data.txt").write_text("41")
    return Job(
        code="print('value:', int(open('data.txt').read()) + 1)",
        program="prog.py",
        command=("python", "prog.py"),
        workspace=str(workspace),
        seed=0,
        seconds=10,
        memory_mb=256,
    )


class TestMeasuringThroughACommand:
    def test_it_measures_what_a_local_sandbox_measures(self, tmp_path):
        job = a_job(tmp_path)
        far = Command(FAR_SIDE).run(job)
        assert far.ok, far.stderr
        assert far.stdout == Subprocess().run(job).stdout == "value: 42\n"

    def test_a_command_that_fails_stops_the_run(self, tmp_path):
        with pytest.raises(SandboxUnreachable, match="exited 1"):
            Command("false").run(a_job(tmp_path))

    def test_an_answer_that_is_not_a_measurement_stops_the_run(self, tmp_path):
        with pytest.raises(SandboxUnreachable, match="did not answer"):
            Command("echo hello").run(a_job(tmp_path))


class TestWhereAMeasurementWasTaken:
    def a_runner(self, sandbox):
        return TrialRunner(
            program="prog.py",
            command=("python", "prog.py"),
            metrics={"value": "maximize"},
            sandbox=sandbox,
            seeds=(0,),
        )

    def test_another_machine_is_another_measurement(self):
        here = self.a_runner(Subprocess()).task_hash
        assert self.a_runner(Command("ssh box cadence sandbox")).task_hash != here
