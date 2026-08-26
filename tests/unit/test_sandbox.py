import pytest
from pydantic import ValidationError

from cadence.execution.sandboxes.subprocess import (
    Execution,
    Job,
    Sandbox,
    SandboxRun,
    Subprocess,
)
from cadence.states import SandboxRunState


def a_job(code, command=("python", "prog.py"), seconds=10.0, memory_mb=256, **kwargs):
    return Job(
        code=code,
        program="prog.py",
        command=command,
        seed=0,
        seconds=seconds,
        memory_mb=memory_mb,
        **kwargs,
    )


PRINTS = "print('value: 3')"
SPINS = "while True:\n    pass"
EXPLODES = "raise ValueError('boom')"
EATS_MEMORY = "x = bytearray(400 * 1024 * 1024)"
SPAWNS_A_CHILD = """\
import subprocess, sys
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
while True:
    pass
"""


class TestRunningACommand:
    def test_the_protocol_is_satisfied(self):
        assert isinstance(Subprocess(), Sandbox)

    def test_a_working_program_succeeds(self):
        assert Subprocess().run(a_job(PRINTS)).ok

    def test_what_it_printed_comes_back(self):
        assert Subprocess().run(a_job(PRINTS)).stdout.strip() == "value: 3"

    def test_it_reports_how_long_it_took(self):
        assert Subprocess().run(a_job(PRINTS)).duration_ms > 0

    def test_a_program_that_raises_is_not_ok(self):
        execution = Subprocess().run(a_job(EXPLODES))
        assert not execution.ok
        assert execution.exit_status != 0

    def test_the_traceback_is_kept(self):
        assert "boom" in Subprocess().run(a_job(EXPLODES)).stderr

    def test_the_command_can_be_anything(self):
        execution = Subprocess().run(a_job("unused", command=("echo", "value: 9")))
        assert execution.stdout.strip() == "value: 9"


class TestLimits:
    def test_a_program_that_never_stops_is_killed(self):
        assert Subprocess().run(a_job(SPINS, seconds=1.0)).timed_out

    def test_a_timeout_is_not_mistaken_for_success(self):
        assert not Subprocess().run(a_job(SPINS, seconds=1.0)).ok

    def test_it_gives_up_near_the_deadline_rather_than_hanging(self):
        assert Subprocess().run(a_job(SPINS, seconds=1.0)).duration_ms < 5000

    def test_a_program_that_eats_memory_is_stopped(self):
        assert not Subprocess().run(a_job(EATS_MEMORY, memory_mb=64)).ok

    def test_a_child_process_does_not_outlive_the_kill(self):
        execution = Subprocess().run(a_job(SPAWNS_A_CHILD, seconds=1.0))
        assert execution.timed_out
        assert execution.duration_ms < 5000


class TestTheWorkspace:
    def test_the_program_cannot_see_our_environment(self, monkeypatch):
        monkeypatch.setenv("CADENCE_SECRET", "hunter2")
        peek = "import os\nprint('value:', os.environ.get('CADENCE_SECRET', 0))"
        assert Subprocess().run(a_job(peek)).stdout.strip() == "value: 0"

    def test_the_seed_is_offered_to_the_program(self):
        peek = "import os\nprint('value:', os.environ['CADENCE_SEED'])"
        assert Subprocess().run(a_job(peek)).stdout.strip() == "value: 0"

    def test_it_runs_somewhere_else(self):
        peek = "import os\nprint(os.getcwd())"
        assert "cadence-" in Subprocess().run(a_job(peek)).stdout

    def test_the_workspace_is_cleaned_up(self):
        import os

        peek = "import os\nprint(os.getcwd())"
        where = Subprocess().run(a_job(peek)).stdout.strip()
        assert not os.path.exists(where)

    def test_a_repo_is_copied_in(self, tmp_path):
        (tmp_path / "helper.py").write_text("ANSWER = 7")
        job = a_job("from helper import ANSWER\nprint('value:', ANSWER)")
        execution = Subprocess().run(
            job.model_copy(update={"workspace": str(tmp_path)})
        )
        assert execution.stdout.strip() == "value: 7"

    def test_the_candidate_overwrites_the_program_in_the_copy(self, tmp_path):
        (tmp_path / "prog.py").write_text("print('value: 1')")
        execution = Subprocess().run(
            a_job("print('value: 2')").model_copy(update={"workspace": str(tmp_path)})
        )
        assert execution.stdout.strip() == "value: 2"

    def test_the_original_repo_is_left_alone(self, tmp_path):
        original = tmp_path / "prog.py"
        original.write_text("print('value: 1')")
        Subprocess().run(
            a_job("print('value: 2')").model_copy(update={"workspace": str(tmp_path)})
        )
        assert original.read_text() == "print('value: 1')"


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
            a_job(PRINTS, seconds=0)

    def test_a_job_needs_a_positive_memory_cap(self):
        with pytest.raises(ValidationError):
            a_job(PRINTS, memory_mb=0)

    def test_a_job_needs_a_command(self):
        with pytest.raises(ValidationError):
            a_job(PRINTS, command=())

    def test_a_job_survives_json(self):
        job = a_job(PRINTS)
        assert Job.model_validate_json(job.model_dump_json()) == job

    def test_an_execution_survives_json(self):
        execution = Subprocess().run(a_job(PRINTS))
        assert Execution.model_validate_json(execution.model_dump_json()) == execution

    def test_a_job_cannot_be_edited(self):
        with pytest.raises(ValidationError):
            a_job(PRINTS).seconds = 99.0


class TestRunningOutOfMemoryIsNotJustACrash:
    def test_an_allocation_past_the_cap_is_named_out_of_memory(self):
        execution = Subprocess().run(
            a_job("x = bytearray(500 * 1024 * 1024)", memory_mb=64)
        )
        assert not execution.ok
        assert execution.out_of_memory

    def test_an_ordinary_crash_is_not_out_of_memory(self):
        execution = Subprocess().run(a_job("raise ValueError('nope')"))
        assert not execution.ok
        assert not execution.out_of_memory

    def test_a_timeout_is_not_out_of_memory(self):
        execution = Subprocess().run(a_job("while True: pass", seconds=0.5))
        assert execution.timed_out
        assert not execution.out_of_memory

    def test_a_clean_run_is_not_out_of_memory(self):
        assert not Subprocess().run(a_job(PRINTS)).out_of_memory
