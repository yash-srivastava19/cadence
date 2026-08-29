"""Killing a run and picking it up again.

The reason every table exists. A crash at trial 400 of 500 should cost one
trial, not four hundred, and should not buy an answer twice.
"""

import os

import pytest

OWNER = os.environ.get("TEST_DATABASE_URL")

if not OWNER:
    pytest.skip(
        "needs TEST_DATABASE_URL; run 'docker compose up -d'", allow_module_level=True
    )

sa = pytest.importorskip("sqlalchemy", reason="run 'pip install -e .'")

from cadence.control.backends import Scripted  # noqa: E402
from cadence.control.experiment import Experiment  # noqa: E402
from cadence.control.methods.evolution import Evolution  # noqa: E402
from cadence.control.model import Model  # noqa: E402
from cadence.control.objectives.ranking import WeightedSum  # noqa: E402
from cadence.control.recall import Recorded  # noqa: E402
from cadence.control.restore import resume_from  # noqa: E402
from cadence.control.storage import model_calls, trials  # noqa: E402
from cadence.execution.runner import TrialRunner  # noqa: E402
from cadence.execution.sandboxes.subprocess import Subprocess  # noqa: E402
from cadence.lifecycle.states import RunState  # noqa: E402
from tests.factories import BASELINE, a_manifest  # noqa: E402
from tests.integration.test_journal import (  # noqa: E402
    IMPROVES,
    IMPROVES_MORE,
    owner_engine,
    session,
)

__all__ = ["owner_engine", "session"]

RUN = "interrupted"


def an_experiment(session, *responses, budget=1):
    """A run that remembers, and can be handed the answers it will get."""
    return Experiment(
        run_id=RUN,
        manifest=a_manifest(),
        method=Evolution(objective=WeightedSum(value=1.0)),
        model=Model(backend=Scripted(*responses), calls=Recorded(session, RUN)),
        runner=TrialRunner(
            program="prog.py",
            command=("python", "prog.py"),
            metrics={"value": "maximize"},
            sandbox=Subprocess(),
            seeds=(0,),
        ),
        seeds=[BASELINE],
        budget=budget,
        resumed=resume_from(session, RUN),
    )


@pytest.fixture
def journal(session):
    from cadence.control.journal import Journal
    from cadence.observe.signals import cadence

    stop = cadence.record(Journal(session).record)
    yield
    stop()


@pytest.fixture
def interrupted(session, journal):
    """A run that really happened, then stopped.

    The trial ran and was recorded. Putting the run back to running is what a
    killed process leaves behind: rows, and no more.
    """
    an_experiment(session, IMPROVES, budget=1).run()
    _running(session)
    return session


@pytest.fixture
def died_mid_trial(session, journal):
    """A run whose process died between asking a model and using the answer.

    The model_calls row is done -- we paid and the reply came back -- and the
    trial never reached measured, which is exactly the case the write-ahead
    exists to make recoverable.
    """
    an_experiment(session, IMPROVES, budget=1).run()
    session.execute(
        sa.update(trials).where(trials.c.run_id == RUN).values(status="prompted")
    )
    _running(session)
    return session


class TestWhatTheDatabaseOffersBack:
    def test_a_finished_run_is_not_resumable(self, session, journal):
        """It has nothing left to do, and starting again under its id would
        write a second account of it."""
        an_experiment(session, IMPROVES, budget=1).run()
        assert resume_from(session, RUN) is None

    def test_an_unfinished_one_is(self, interrupted):
        assert resume_from(interrupted, RUN) is not None

    def test_it_offers_back_what_was_already_scored(self, interrupted):
        assert len(resume_from(interrupted, RUN).history.results) == 1

    def test_it_counts_the_trials_that_are_over(self, interrupted):
        assert resume_from(interrupted, RUN).trials == 1

    def test_a_trial_still_in_flight_does_not_count_as_over(self, died_mid_trial):
        """So the next trial takes its seq and redoes it, rather than
        numbering past a row nothing will ever finish."""
        assert resume_from(died_mid_trial, RUN).trials == 0


class TestPickingItUpAgain:
    def test_it_carries_on_rather_than_starting_over(self, interrupted, journal):
        report = an_experiment(interrupted, IMPROVES_MORE, budget=2).run()
        assert report.trials == 2

    def test_the_second_trial_gets_the_next_seq(self, interrupted, journal):
        an_experiment(interrupted, IMPROVES_MORE, budget=2).run()
        seqs = (
            interrupted.execute(
                sa.select(trials.c.seq)
                .where(trials.c.run_id == RUN)
                .order_by(trials.c.seq)
            )
            .scalars()
            .all()
        )
        assert seqs == [0, 1]

    def test_it_keeps_what_the_first_run_scored(self, interrupted, journal):
        report = an_experiment(interrupted, IMPROVES_MORE, budget=2).run()
        assert report.scored == 2

    def test_the_tape_says_it_was_resumed_not_started_twice(self, interrupted, journal):
        from cadence.control.storage import events

        an_experiment(interrupted, IMPROVES_MORE, budget=2).run()
        kinds = (
            interrupted.execute(sa.select(events.c.type).where(events.c.run_id == RUN))
            .scalars()
            .all()
        )
        assert kinds.count("RunStarted") == 1
        assert kinds.count("RunResumed") == 1


class TestItDoesNotPayTwice:
    def test_a_redone_trial_is_given_the_answer_it_already_bought(
        self, died_mid_trial, journal
    ):
        """The scripted backend is handed no answers at all. If the redone
        trial needed a model call it would fail, and it does not: the question
        it asks is the question trial 0 asked, and that answer is in
        model_calls."""
        experiment = an_experiment(died_mid_trial, budget=1)
        report = experiment.run()
        assert experiment.model.backend.prompts == []
        assert report.scored == 1

    def test_the_tape_says_the_call_was_replayed(self, died_mid_trial, journal):
        from cadence.control.storage import events

        an_experiment(died_mid_trial, budget=1).run()
        called = (
            died_mid_trial.execute(
                sa.select(events.c.payload).where(events.c.type == "ModelCalled")
            )
            .scalars()
            .all()
        )
        assert [payload["replayed"] for payload in called] == [False, True]

    def test_the_recorded_call_is_the_one_that_was_made(self, interrupted):
        stored = (
            interrupted.execute(
                sa.select(model_calls.c.response, model_calls.c.status).where(
                    model_calls.c.run_id == RUN
                )
            )
            .mappings()
            .all()
        )
        assert stored[0]["status"] == "done"
        assert "value: 45" in stored[0]["response"]


def _running(session):
    """Put the run back in the state a killed process would have left it."""
    session.execute(
        sa.update(sa.table("runs", sa.column("id"), sa.column("status")))
        .where(sa.column("id") == RUN)
        .values(status=RunState.RUNNING.value)
    )
