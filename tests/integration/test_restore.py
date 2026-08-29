"""Run something, then read it back and check it is the same run.

These are the specs that say the database is a record rather than a pile of
rows: everything asserted here is read from Postgres, and compared against
what the run reported in memory.
"""

import os

import pytest

OWNER = os.environ.get("TEST_DATABASE_URL")

if not OWNER:
    pytest.skip(
        "needs TEST_DATABASE_URL; run 'docker compose up -d'", allow_module_level=True
    )

sa = pytest.importorskip("sqlalchemy", reason="run 'pip install -e .'")

from cadence.control.restore import history_of, seeds_of, status_of  # noqa: E402
from cadence.core.verdict import Scored  # noqa: E402
from cadence.lifecycle.states import RunState  # noqa: E402
from tests.factories import BASELINE  # noqa: E402
from tests.integration.test_journal import (  # noqa: E402
    CRASHES,
    IMPROVES,
    IMPROVES_MORE,
    NONSENSE,
    journalled,
    owner_engine,
    session,
)

__all__ = ["journalled", "owner_engine", "session"]


class TestARunThatIsNotThere:
    def test_it_has_no_status(self, session):
        assert status_of(session, "never-ran") is None

    def test_it_has_no_history(self, session):
        assert history_of(session, "never-ran") is None


class TestReadingBackAFinishedRun:
    def test_the_status_is_what_the_run_reported(self, session, journalled):
        report = journalled(IMPROVES)
        assert status_of(session, "h1") == report.status == RunState.FINISHED

    def test_the_seeds_are_the_programs_it_started_from(self, session, journalled):
        journalled(IMPROVES)
        assert seeds_of(session, "h1") == (BASELINE,)

    def test_the_history_has_one_result(self, session, journalled):
        journalled(IMPROVES)
        assert len(history_of(session, "h1").results) == 1

    def test_the_result_is_the_program_the_run_ended_with(self, session, journalled):
        report = journalled(IMPROVES)
        assert history_of(session, "h1").results[0].code == report.program

    def test_the_result_carries_the_metrics_it_scored(self, session, journalled):
        report = journalled(IMPROVES)
        assert history_of(session, "h1").results[0].metrics == report.metrics

    def test_the_history_is_the_one_the_method_would_have_built(
        self, session, journalled
    ):
        """Not merely equivalent -- the same value. A search method takes a
        RunHistory and cannot tell which side of the database it came from."""
        report = journalled(IMPROVES)
        restored = history_of(session, "h1")
        assert restored.run_id == "h1"
        assert restored.seeds == (BASELINE,)
        assert restored.index == report.trials


class TestTheOrderIsTheOrderItHappened:
    def test_results_come_back_in_the_order_they_were_tried(self, session, journalled):
        journalled(IMPROVES, IMPROVES_MORE, budget=2)
        scored = [
            result.metrics["value"] for result in history_of(session, "h1").results
        ]
        assert scored == [45.0, 99.0]


class TestWhatDidNotProduceACandidate:
    def test_an_abandoned_trial_leaves_no_result(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert history_of(session, "h1").results == ()

    def test_but_the_seeds_are_still_there_to_carry_on_from(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert seeds_of(session, "h1") == (BASELINE,)


class TestAFailureIsRestoredAsAFailure:
    def test_a_crashed_candidate_comes_back_failed(self, session, journalled):
        journalled(CRASHES)
        verdict = history_of(session, "h1").results[0].verdict
        assert not isinstance(verdict, Scored)

    def test_it_keeps_the_reason_it_failed(self, session, journalled):
        journalled(CRASHES)
        verdict = history_of(session, "h1").results[0].verdict
        assert "ValueError" in verdict.reason
