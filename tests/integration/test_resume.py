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
from tests.factories import BASELINE, a_manifest, asked, present  # noqa: E402
from tests.integration.test_journal import (  # noqa: E402
    CRASHES,
    IMPROVES,
    IMPROVES_MORE,
    NONSENSE,
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
        assert len(present(resume_from(interrupted, RUN)).history.results) == 1

    def test_it_counts_the_trials_that_are_over(self, interrupted):
        assert present(resume_from(interrupted, RUN)).trials == 1

    def test_a_trial_still_in_flight_does_not_count_as_over(self, died_mid_trial):
        """So the next trial takes its seq and redoes it, rather than
        numbering past a row nothing will ever finish."""
        assert present(resume_from(died_mid_trial, RUN)).trials == 0


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
        assert asked(experiment) == []
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

    def test_a_retry_that_was_paid_for_is_replayed_too(self, session, journal):
        """A trial that was asked again bought two answers, not one. Only the
        first was ever closed, so a resumed run re-bought the retry -- the
        second answer was in the database the whole time under its own key."""
        an_experiment(session, NONSENSE, IMPROVES, budget=1).run()
        session.execute(
            sa.update(trials).where(trials.c.run_id == RUN).values(status="prompted")
        )
        _running(session)

        experiment = an_experiment(session, budget=1)
        report = experiment.run()
        assert asked(experiment) == []
        assert report.scored == 1

    def test_both_answers_come_back_marked_replayed(self, session, journal):
        from cadence.control.storage import events

        an_experiment(session, NONSENSE, IMPROVES, budget=1).run()
        session.execute(
            sa.update(trials).where(trials.c.run_id == RUN).values(status="prompted")
        )
        _running(session)
        an_experiment(session, budget=1).run()

        replayed = (
            session.execute(
                sa.select(events.c.payload).where(events.c.type == "ModelCalled")
            )
            .scalars()
            .all()
        )
        assert [payload["replayed"] for payload in replayed] == [
            False,
            False,
            True,
            True,
        ]

    def test_a_resumed_run_is_not_billed_for_what_it_replayed(
        self, died_mid_trial, journal
    ):
        """calls counts the asking, usd counts the buying. A run that bought
        nothing has no bill, even though it made a call."""
        report = an_experiment(died_mid_trial, budget=1).run()
        assert report.spend.calls == 1
        assert report.spend.replayed == 1
        assert report.spend.usd is None

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


class TestAQuarantinedCandidateIsNotOfferedBack:
    def test_it_is_left_out_of_the_history(self, session, journal):
        """The search method never learns quarantine exists. It is handed a
        history without the poison in it, which is how it stays a pure
        function of what it is given."""
        from cadence.control.restore import history_of
        from cadence.control.storage import candidates

        an_experiment(session, CRASHES, budget=1).run()
        assert len(present(history_of(session, RUN)).results) == 1
        session.execute(
            sa.update(candidates)
            .where(candidates.c.parent_id.isnot(None))
            .values(status="quarantined")
        )
        assert present(history_of(session, RUN)).results == ()


class TestResumingIsAskedForNeverInferred:
    """build() used to pick a run up whenever its id was already in the
    database. That is fine alone on a laptop and wrong the moment two people
    share one: everybody's run was called "local", so the second person to
    start one silently continued the first person's experiment."""

    def _built(self, session, root, resume):
        from pathlib import Path

        from cadence.control.manifest import load
        from cadence.control.registry import build

        return build(
            load(Path(root)),
            Path(root),
            RUN,
            backend=Scripted(IMPROVES_MORE),
            session=session,
            resume=resume,
        )

    @pytest.fixture
    def a_project(self, tmp_path):
        (tmp_path / ".cadence").write_text(
            "api_version: cadence/v1alpha2\nprogram: prog.py\n"
            "metrics:\n  value: maximize\nbudget:\n  trials: 1\n"
        )
        (tmp_path / "prog.py").write_text(
            "# CADENCE:BEGIN\nprint('value: 1')\n# CADENCE:END\n"
        )
        return tmp_path

    def test_an_interrupted_run_is_not_picked_up_by_default(
        self, interrupted, a_project
    ):
        assert self._built(interrupted, a_project, resume=False).resumed is None

    def test_asking_picks_it_up(self, interrupted, a_project):
        assert self._built(interrupted, a_project, resume=True).resumed is not None

    def test_what_it_picks_up_is_what_was_learned(self, interrupted, a_project):
        built = self._built(interrupted, a_project, resume=True)
        assert len(present(built.resumed).history.results) == 1

    def test_asking_to_resume_a_run_nobody_recorded_finds_nothing(
        self, session, a_project
    ):
        assert self._built(session, a_project, resume=True).resumed is None
