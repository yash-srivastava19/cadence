import pytest

from cadence.exceptions import PatchError
from cadence.control.patcher import apply_patch
from cadence.execution.runner import TrialRunner
from cadence.execution.sandboxes.subprocess import Subprocess
from cadence.verdict import Outcome

BASELINE = "print('value: 0')"
BETTER = "print('value: 9')"


def a_runner(metrics=None, **kwargs):
    return TrialRunner(
        program="prog.py",
        command=("python", "prog.py"),
        metrics=metrics or {"value": "maximize"},
        sandbox=Subprocess(),
        seeds=kwargs.pop("seeds", (0,)),
        **kwargs,
    )


def a_patch(*body):
    return ("--- a/s.py", "+++ b/s.py", "@@ -1,1 +1,1 @@", *body)


class TestPatching:
    def test_a_replacement_lands(self):
        patch = a_patch(f"-{BASELINE}", f"+{BETTER}")
        assert apply_patch(BASELINE, patch) == BETTER

    def test_a_patch_that_matches_nothing_says_which_line(self):
        patch = a_patch("-print('nope')", f"+{BETTER}")
        with pytest.raises(PatchError, match="nope"):
            apply_patch(BASELINE, patch)

    def test_a_patch_with_no_hunks_raises(self):
        with pytest.raises(PatchError, match="no hunks"):
            apply_patch(BASELINE, ("--- a/s.py", "+++ b/s.py"))

    def test_prose_instead_of_a_patch_raises(self):
        with pytest.raises(PatchError, match="no hunks"):
            apply_patch(BASELINE, ("I would change the loop.",))


class TestScoring:
    def test_a_working_candidate_is_scored(self):
        assert a_runner().try_(BETTER).is_scored

    def test_the_metric_comes_from_what_the_program_printed(self):
        assert a_runner().try_(BETTER).metrics["value"] == 9.0

    def test_the_verdict_names_the_code_it_measured(self):
        from cadence.verdict import fingerprint

        assert a_runner().try_(BETTER).fingerprint == fingerprint(BETTER)

    def test_several_metrics_come_back(self):
        code = "print('value: 2')\nprint('cost: 5')"
        verdict = a_runner(metrics={"value": "maximize", "cost": "minimize"}).try_(code)
        assert verdict.metrics == {"value": 2.0, "cost": 5.0}

    def test_readings_are_averaged_across_seeds(self):
        code = "import os\nprint('value:', int(os.environ['CADENCE_SEED']))"
        verdict = a_runner(seeds=(0, 2)).try_(code)
        assert verdict.metrics["value"] == 1.0

    def test_a_runner_needs_a_seed(self):
        with pytest.raises(ValueError):
            a_runner(seeds=())

    def test_a_runner_needs_a_metric(self):
        with pytest.raises(ValueError):
            TrialRunner(
                program="prog.py",
                command=("python", "prog.py"),
                metrics={},
                sandbox=Subprocess(),
                seeds=(0,),
            )


class TestFailuresAreDistinguished:
    def test_a_crash_is_a_crash(self):
        verdict = a_runner().try_("raise ValueError('x')")
        assert verdict.outcome is Outcome.CRASHED

    def test_a_crash_keeps_the_reason(self):
        verdict = a_runner().try_("raise ValueError('x')")
        assert "ValueError" in verdict.reason

    def test_a_timeout_is_a_timeout(self):
        spins = "while True:\n    pass"
        verdict = a_runner(seconds=1.0).try_(spins)
        assert verdict.outcome is Outcome.TIMED_OUT

    def test_a_program_that_reports_nothing_is_invalid(self):
        verdict = a_runner().try_("print('all done')")
        assert verdict.outcome is Outcome.INVALID

    def test_it_says_which_metric_was_missing(self):
        verdict = a_runner().try_("print('all done')")
        assert "value" in verdict.reason

    def test_one_bad_seed_fails_the_whole_verdict(self):
        code = (
            "import os\n"
            "if os.environ['CADENCE_SEED'] == '2': raise ValueError('x')\n"
            "print('value: 1')"
        )
        assert not a_runner(seeds=(0, 2)).try_(code).is_scored


class TestOutOfMemoryReachesTheVerdict:
    def test_a_greedy_candidate_is_out_of_memory_not_crashed(self):
        verdict = a_runner(memory_mb=64).try_("x = bytearray(500 * 1024 * 1024)")
        assert verdict.outcome is Outcome.OUT_OF_MEMORY
        assert "memory" in verdict.reason
