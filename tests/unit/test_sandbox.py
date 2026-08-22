import json

import pytest
from pydantic import ValidationError

from cadence.sandbox import Execution, Job, Sandbox, SandboxRun, Subprocess
from cadence.states import SandboxRunState


def a_job(code, seconds=10.0, memory_mb=256, **kwargs):
    return Job(
        code=code,
        entry_point="solve",
        seed=0,
        seconds=seconds,
        memory_mb=memory_mb,
        **kwargs,
    )


RETURNS_A_LIST = "def solve(): return [1, 2, 3]"
SPINS = "def solve():\n    while True:\n        pass"
EXPLODES = "def solve(): raise ValueError('boom')"
EATS_MEMORY = "def solve():\n    x = bytearray(400 * 1024 * 1024)\n    return len(x)"
SPAWNS_A_CHILD = """\
def solve():
    import subprocess, sys
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    while True:
        pass
"""


class TestRunningSomething:
    def test_the_protocol_is_satisfied(self):
        assert isinstance(Subprocess(), Sandbox)

    def test_a_working_program_succeeds(self):
        execution = Subprocess().run(a_job(RETURNS_A_LIST))
        assert execution.ok

    def test_its_return_value_comes_back(self):
        execution = Subprocess().run(a_job(RETURNS_A_LIST))
        assert json.loads(execution.stdout) == [1, 2, 3]

    def test_it_reports_how_long_it_took(self):
        assert Subprocess().run(a_job(RETURNS_A_LIST)).duration_ms > 0

    def test_a_program_that_raises_is_not_ok(self):
        execution = Subprocess().run(a_job(EXPLODES))
        assert not execution.ok
        assert execution.exit_status != 0

    def test_the_traceback_is_kept(self):
        assert "boom" in Subprocess().run(a_job(EXPLODES)).stderr


class TestLimits:
    def test_a_program_that_never_stops_is_killed(self):
        execution = Subprocess().run(a_job(SPINS, seconds=1.0))
        assert execution.timed_out

    def test_a_timeout_is_not_mistaken_for_success(self):
        assert not Subprocess().run(a_job(SPINS, seconds=1.0)).ok

    def test_it_gives_up_near_the_deadline_rather_than_hanging(self):
        execution = Subprocess().run(a_job(SPINS, seconds=1.0))
        assert execution.duration_ms < 5000

    def test_a_program_that_eats_memory_is_stopped(self):
        execution = Subprocess().run(a_job(EATS_MEMORY, memory_mb=64))
        assert not execution.ok

    def test_a_child_process_does_not_outlive_the_kill(self):
        execution = Subprocess().run(a_job(SPAWNS_A_CHILD, seconds=1.0))
        assert execution.timed_out
        assert execution.duration_ms < 5000


class TestIsolation:
    def test_the_program_cannot_see_our_environment(self):
        peek = "import os\ndef solve(): return os.environ.get('CADENCE_SECRET')"
        execution = Subprocess().run(a_job(peek))
        assert json.loads(execution.stdout) is None

    def test_it_runs_somewhere_else(self):
        peek = "import os\ndef solve(): return os.getcwd()"
        execution = Subprocess().run(a_job(peek))
        assert "cadence-" in json.loads(execution.stdout)

    def test_the_workspace_is_cleaned_up(self):
        import os

        peek = "import os\ndef solve(): return os.getcwd()"
        workspace = json.loads(Subprocess().run(a_job(peek)).stdout)
        assert not os.path.exists(workspace)


class TestTheRunItself:
    def test_it_starts_running(self):
        assert SandboxRun().status == SandboxRunState.RUNNING

    def test_a_reaped_run_is_final(self):
        run = SandboxRun()
        run.reap()
        assert run.is_final

    def test_an_orphan_can_still_be_killed(self):
        run = SandboxRun()
        run.orphan()
        assert run.may_kill
        run.kill()
        assert run.status == SandboxRunState.KILLED

    def test_a_reaped_run_cannot_be_killed(self):
        run = SandboxRun()
        run.reap()
        assert not run.may_kill


class TestTheJobAndTheExecution:
    def test_a_job_needs_a_positive_deadline(self):
        with pytest.raises(ValidationError):
            a_job(RETURNS_A_LIST, seconds=0)

    def test_a_job_needs_a_positive_memory_cap(self):
        with pytest.raises(ValidationError):
            a_job(RETURNS_A_LIST, memory_mb=0)

    def test_a_job_survives_json(self):
        job = a_job(RETURNS_A_LIST)
        assert Job.model_validate_json(job.model_dump_json()) == job

    def test_an_execution_survives_json(self):
        execution = Subprocess().run(a_job(RETURNS_A_LIST))
        assert Execution.model_validate_json(execution.model_dump_json()) == execution

    def test_a_job_cannot_be_edited(self):
        with pytest.raises(ValidationError):
            a_job(RETURNS_A_LIST).seconds = 99.0
