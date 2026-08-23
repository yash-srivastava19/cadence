import pytest

from cadence.entities import Candidate
from cadence.exceptions import PatchError
from cadence.patcher import apply_patch
from cadence.runner import TrialRunner
from cadence.sandbox import Subprocess
from cadence.verdict import Outcome

BASELINE = "def solve(a, b):\n    return 0"
BETTER = "def solve(a, b):\n    return a + b"


class Adder:
    entry_point = "solve"
    baseline = BASELINE

    def inputs(self, seed):
        return (seed + 1, seed + 2)

    def score(self, output, inputs):
        return {"total": float(output), "error": float(abs(sum(inputs) - output))}


class BrokenVerifier(Adder):
    def score(self, output, inputs):
        raise ZeroDivisionError("the user's scoring script is wrong")


class SilentVerifier(Adder):
    def score(self, output, inputs):
        return {}


def a_runner(task=None, **kwargs):
    return TrialRunner(task=task or Adder(), sandbox=Subprocess(), **kwargs)


def a_patch(*body):
    return ("--- a/s.py", "+++ b/s.py", "@@ -1,2 +1,2 @@", *body)


class TestPatching:
    def test_a_replacement_lands(self):
        patch = a_patch(" def solve(a, b):", "-    return 0", "+    return a + b")
        assert apply_patch(BASELINE, patch) == BETTER

    def test_an_addition_lands(self):
        patch = (
            "--- a/s.py",
            "+++ b/s.py",
            "@@ -1,2 +1,3 @@",
            " def solve(a, b):",
            "     return 0",
            "+# a note",
        )
        assert apply_patch(BASELINE, patch).endswith("# a note")

    def test_several_hunks_all_land(self):
        patch = (
            "--- a/s.py",
            "+++ b/s.py",
            "@@ -1,1 +1,1 @@",
            "-def solve(a, b):",
            "+def solve(x, y):",
            "@@ -2,1 +2,1 @@",
            "-    return 0",
            "+    return 1",
        )
        assert apply_patch(BASELINE, patch) == "def solve(x, y):\n    return 1"

    def test_a_patch_that_matches_nothing_says_which_line(self):
        patch = a_patch(" def solve(a, b):", "-    return 99", "+    return 1")
        with pytest.raises(PatchError, match="return 99"):
            apply_patch(BASELINE, patch)

    def test_a_patch_with_no_hunks_raises(self):
        with pytest.raises(PatchError, match="no hunks"):
            apply_patch(BASELINE, ("--- a/s.py", "+++ b/s.py"))

    def test_prose_instead_of_a_patch_raises(self):
        with pytest.raises(PatchError, match="no hunks"):
            apply_patch(BASELINE, ("I would change the loop.",))


class TestScoring:
    def test_a_working_candidate_is_scored(self):
        verdict = a_runner().try_(Candidate(code=BETTER))
        assert verdict.is_scored

    def test_the_metrics_come_from_the_task(self):
        verdict = a_runner().try_(Candidate(code=BETTER))
        assert verdict.metrics["error"] == 0.0

    def test_the_verdict_names_the_candidate_it_measured(self):
        candidate = Candidate(code=BETTER)
        assert a_runner().try_(candidate).fingerprint == candidate.fingerprint

    def test_readings_are_averaged_across_seeds(self):
        verdict = a_runner(seeds=(0, 1)).try_(Candidate(code=BETTER))
        assert verdict.metrics["total"] == 4.0

    def test_a_runner_needs_a_seed(self):
        with pytest.raises(ValueError):
            a_runner(seeds=())


class TestFailuresAreDistinguished:
    def test_a_crash_is_a_crash(self):
        verdict = a_runner().try_(
            Candidate(code="def solve(a, b): raise ValueError('x')")
        )
        assert verdict.outcome is Outcome.CRASHED

    def test_a_crash_keeps_the_reason(self):
        verdict = a_runner().try_(
            Candidate(code="def solve(a, b): raise ValueError('x')")
        )
        assert "ValueError" in verdict.reason

    def test_a_timeout_is_a_timeout(self):
        spins = "def solve(a, b):\n    while True:\n        pass"
        verdict = a_runner(seconds=1.0).try_(Candidate(code=spins))
        assert verdict.outcome is Outcome.TIMED_OUT

    def test_output_that_will_not_serialize_is_invalid(self):
        weird = "def solve(a, b): return object()"
        assert a_runner().try_(Candidate(code=weird)).outcome is Outcome.INVALID

    def test_one_bad_seed_fails_the_whole_verdict(self):
        only_first = (
            "def solve(a, b):\n    if a > 1: raise ValueError('x')\n    return 0"
        )
        verdict = a_runner(seeds=(0, 5)).try_(Candidate(code=only_first))
        assert not verdict.is_scored


class TestTheVerifierIsNotTheCandidate:
    def test_a_broken_verifier_is_its_own_outcome(self):
        verdict = a_runner(task=BrokenVerifier()).try_(Candidate(code=BETTER))
        assert verdict.outcome is Outcome.VERIFIER_ERROR

    def test_it_escalates_rather_than_scoring_the_floor(self):
        verdict = a_runner(task=BrokenVerifier()).try_(Candidate(code=BETTER))
        assert verdict.escalates
        assert not verdict.is_scored

    def test_it_names_the_error_the_user_has_to_fix(self):
        verdict = a_runner(task=BrokenVerifier()).try_(Candidate(code=BETTER))
        assert "ZeroDivisionError" in verdict.reason

    def test_a_verifier_that_scores_nothing_is_also_an_error(self):
        verdict = a_runner(task=SilentVerifier()).try_(Candidate(code=BETTER))
        assert verdict.outcome is Outcome.VERIFIER_ERROR

    def test_a_candidate_crash_is_not_blamed_on_the_verifier(self):
        verdict = a_runner().try_(
            Candidate(code="def solve(a, b): raise ValueError('x')")
        )
        assert not verdict.escalates
