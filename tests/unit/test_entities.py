import pytest
from statemachine.exceptions import TransitionNotAllowed

from cadence.control.entities import Candidate, Run, Trial, fingerprint, trial_id
from cadence.states import CandidateState, RunState, TrialState
from cadence.verdict import Scored


def a_candidate(code="def pack(): return []"):
    return Candidate(code=code)


def a_trial():
    return Trial(id=trial_id("h1", 0, 0), parent=a_candidate())


class TestFingerprint:
    def test_the_same_code_gives_the_same_fingerprint(self):
        assert fingerprint("x = 1") == fingerprint("x = 1")

    def test_different_code_gives_a_different_fingerprint(self):
        assert fingerprint("x = 1") != fingerprint("x = 2")

    def test_a_candidate_fingerprints_its_own_code(self):
        candidate = a_candidate("x = 1")
        assert candidate.fingerprint == fingerprint("x = 1")

    def test_it_is_the_key_a_verdict_carries(self):
        candidate = a_candidate()
        verdict = Scored(fingerprint=candidate.fingerprint, metrics={"value": 1.0})
        assert verdict.fingerprint == candidate.fingerprint


class TestTrialIdIsDerived:
    def test_the_same_position_gives_the_same_id(self):
        assert trial_id("h1", 2, 5) == trial_id("h1", 2, 5)

    def test_it_names_its_run_and_position(self):
        assert trial_id("h1", 2, 5) == "h1/2/5"

    def test_a_trial_cannot_be_built_without_one(self):
        with pytest.raises(TypeError):
            Trial(parent=a_candidate())


class TestACandidate:
    def test_it_starts_alive(self):
        assert a_candidate().is_alive

    def test_it_can_be_retired(self):
        candidate = a_candidate()
        candidate.retire()
        assert candidate.status == CandidateState.RETIRED

    def test_it_is_not_quarantined_for_one_crash(self):
        candidate = a_candidate()
        candidate.crashed()
        assert not candidate.may_quarantine

    def test_it_is_quarantined_once_it_crashes_too_often(self):
        candidate = a_candidate()
        for _ in range(Candidate.crash_limit):
            candidate.crashed()
        assert candidate.may_quarantine
        candidate.quarantine()
        assert candidate.status == CandidateState.QUARANTINED

    def test_quarantine_is_refused_before_the_limit(self):
        with pytest.raises(TransitionNotAllowed):
            a_candidate().quarantine()

    def test_it_remembers_where_it_came_from(self):
        parent = a_candidate("x = 1")
        child = Candidate(code="x = 2", parent=parent.fingerprint)
        assert child.parent == parent.fingerprint


class TestATrial:
    def test_it_starts_at_the_beginning(self):
        assert a_trial().status == TrialState.STARTED

    def test_the_happy_path_ends_measured(self):
        trial = a_trial()
        trial.prompt()
        trial.generate(proposal="a patch")
        trial.apply_patch(candidate=a_candidate("x = 2"))
        verdict = Scored(
            fingerprint=trial.candidate.fingerprint, metrics={"value": 1.0}
        )
        trial.measure(verdict=verdict)
        assert trial.status == TrialState.MEASURED
        assert trial.verdict is verdict

    def test_a_patch_that_does_not_apply_leaves_it_unusable(self):
        trial = a_trial()
        trial.prompt()
        trial.generate(proposal="a patch")
        trial.reject(reason="no hunks matched")
        assert trial.status == TrialState.UNUSABLE
        assert trial.reason == "no hunks matched"

    def test_retrying_counts(self):
        trial = a_trial()
        trial.prompt()
        trial.retry()
        assert trial.attempts == 1

    def test_the_retry_budget_is_visible_before_it_runs_out(self):
        trial = a_trial()
        trial.prompt()
        for _ in range(Trial.max_attempts):
            assert trial.may_retry
            trial.retry()
        assert not trial.may_retry

    def test_a_spent_budget_refuses_another_retry(self):
        trial = a_trial()
        trial.prompt()
        for _ in range(Trial.max_attempts):
            trial.retry()
        with pytest.raises(TransitionNotAllowed):
            trial.retry()

    def test_it_can_be_abandoned_at_any_live_point(self):
        for step in ("started", "prompted", "generated"):
            trial = a_trial()
            if step != "started":
                trial.prompt()
            if step == "generated":
                trial.generate(proposal="a patch")
            trial.abandon(reason="run cancelled")
            assert trial.status == TrialState.ABANDONED

    def test_it_cannot_be_measured_before_a_patch_applies(self):
        trial = a_trial()
        trial.prompt()
        with pytest.raises(TransitionNotAllowed):
            trial.measure(verdict=None)

    def test_one_recovered_from_storage_carries_on(self):
        trial = Trial(
            id=trial_id("h1", 0, 0),
            parent=a_candidate(),
            status=TrialState.MATERIALIZED,
        )
        assert trial.may_measure
        assert not trial.may_prompt


class TestARun:
    def test_it_starts_pending(self):
        assert Run(id="h1").status == RunState.PENDING

    def test_it_can_be_cancelled_before_it_starts(self):
        run = Run(id="h1")
        run.cancel()
        assert run.status == RunState.CANCELLED

    def test_it_can_pause_and_resume(self):
        run = Run(id="h1")
        run.start()
        run.pause()
        assert run.status == RunState.PAUSED
        run.resume()
        assert run.status == RunState.RUNNING

    def test_finishing_records_the_best(self):
        run = Run(id="h1")
        run.start()
        run.finish(best="abc123")
        assert run.status == RunState.FINISHED
        assert run.best == "abc123"

    def test_failing_records_why(self):
        run = Run(id="h1")
        run.start()
        run.fail(reason="backend unreachable")
        assert run.status == RunState.FAILED
        assert run.reason == "backend unreachable"

    def test_a_run_cannot_fail_without_saying_why(self):
        run = Run(id="h1")
        run.start()
        with pytest.raises(TransitionNotAllowed):
            run.fail(reason="")

    def test_a_finished_run_is_final(self):
        run = Run(id="h1")
        run.start()
        run.finish()
        assert run.is_final

    def test_one_recovered_mid_flight_can_still_be_cancelled(self):
        run = Run(id="h1", status=RunState.RUNNING)
        assert run.may_cancel
        assert not run.may_start
