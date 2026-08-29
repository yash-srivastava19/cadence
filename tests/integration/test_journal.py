"""A real run, against a real database.

The point of these is not that rows appear. It is that what the database says
afterwards is what actually happened -- read back without looking at any of
the objects the run used.
"""

import os

import pytest

OWNER = os.environ.get("TEST_DATABASE_URL")

if not OWNER:
    pytest.skip(
        "needs TEST_DATABASE_URL; run 'docker compose up -d'", allow_module_level=True
    )

sa = pytest.importorskip("sqlalchemy", reason="run 'pip install -e .'")

from sqlalchemy import orm  # noqa: E402

from cadence.control.experiment import Experiment  # noqa: E402
from cadence.control.journal import Journal  # noqa: E402
from cadence.control.methods.evolution import Evolution  # noqa: E402
from cadence.control.model import Model  # noqa: E402
from cadence.control.objectives.ranking import WeightedSum  # noqa: E402
from cadence.control.storage import (  # noqa: E402
    blobs,
    candidates,
    engine,
    events,
    model_calls,
    runs,
    trials,
    verdicts,
)
from cadence.core.identity import fingerprint  # noqa: E402
from cadence.core.verdict import Outcome  # noqa: E402
from cadence.execution.runner import TrialRunner  # noqa: E402
from cadence.execution.sandboxes.subprocess import Subprocess  # noqa: E402
from cadence.lifecycle.states import RunState, TrialState  # noqa: E402
from cadence.observe.signals import cadence  # noqa: E402
from tests.factories import BASELINE, a_manifest  # noqa: E402

IMPROVES = "Here it is.\n```python\nprint('value: 45')\n```"
IMPROVES_MORE = "Better.\n```python\nprint('value: 99')\n```"
CRASHES = "Try this.\n```python\nraise ValueError('the evolved code is broken')\n```"
NONSENSE = "I would change the loop, but here is prose instead."


@pytest.fixture(scope="module")
def owner_engine():
    made = engine(OWNER)
    yield made
    made.dispose()


@pytest.fixture
def session(owner_engine):
    """Rails' transactional fixtures: the run may commit, and none of it
    survives the test."""
    connection = owner_engine.connect()
    outer = connection.begin()
    session = orm.Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def journalled(session):
    """A run that writes itself down. Returns a function that runs it."""
    journal = Journal(session)
    stop = cadence.record(journal.record)

    def run(*responses, run_id="h1", budget=1):
        from cadence.control.backends import Scripted

        experiment = Experiment(
            run_id=run_id,
            manifest=a_manifest(),
            method=Evolution(objective=WeightedSum(value=1.0)),
            model=Model(backend=Scripted(*responses)),
            runner=TrialRunner(
                program="prog.py",
                command=("python", "prog.py"),
                metrics={"value": "maximize"},
                sandbox=Subprocess(),
                seeds=(0,),
            ),
            seeds=[BASELINE],
            budget=budget,
        )
        return experiment.run()

    yield run
    stop()


def rows(session, table, **where):
    statement = sa.select(table)
    for column, value in where.items():
        statement = statement.where(table.c[column] == value)
    return session.execute(statement.order_by(*table.primary_key)).mappings().all()


class TestAFinishedRunWroteItselfDown:
    def test_the_run_is_there(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, runs, id="h1")) == 1

    def test_it_says_the_run_finished(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["status"] == RunState.FINISHED

    def test_it_counted_the_trials(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["trials"] == 1

    def test_it_names_the_best_candidate(self, session, journalled):
        report = journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["best"] == report.best

    def test_it_remembers_which_manifest_produced_it(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["manifest_hash"] == a_manifest().hash


class TestTheTapeIsTheWholeRun:
    def test_every_fact_was_written(self, session, journalled):
        journalled(IMPROVES)
        assert [row["type"] for row in rows(session, events, run_id="h1")] == [
            "RunStarted",
            "TrialStarted",
            "ModelRequested",
            "ModelCalled",
            "ProposalReceived",
            "CandidateBuilt",
            "TrialMeasured",
            "RunFinished",
        ]

    def test_the_tape_is_numbered_from_zero(self, session, journalled):
        journalled(IMPROVES)
        assert [row["seq"] for row in rows(session, events, run_id="h1")] == list(
            range(8)
        )

    def test_a_fact_carries_what_it_was_about(self, session, journalled):
        journalled(IMPROVES)
        measured = [
            row
            for row in rows(session, events, run_id="h1")
            if row["type"] == "TrialMeasured"
        ]
        assert measured[0]["payload"]["verdict"]["metrics"] == {"value": 45.0}

    def test_it_keeps_both_clocks(self, session, journalled):
        journalled(IMPROVES)
        row = rows(session, events, run_id="h1")[0]
        assert row["occurred_at"] <= row["recorded_at"]

    def test_the_run_id_is_a_column_not_a_payload_field(self, session, journalled):
        journalled(IMPROVES)
        assert "run_id" not in rows(session, events, run_id="h1")[0]["payload"]


class TestARunThatFailed:
    def test_it_is_recorded_as_failed(self, session, journalled):
        journalled(run_id="h2")  # no scripted answers at all
        assert rows(session, runs, id="h2")[0]["status"] == RunState.FAILED

    def test_it_says_why(self, session, journalled):
        journalled(run_id="h2")
        assert "ran out of responses" in rows(session, runs, id="h2")[0]["reason"]

    def test_the_tape_still_ends_with_the_run_finishing(self, session, journalled):
        journalled(run_id="h2")
        assert rows(session, events, run_id="h2")[-1]["type"] == "RunFinished"


class TestTheCandidatesAreThere:
    def test_the_seed_and_the_child_are_both_candidates(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, candidates, run_id="h1")) == 2

    def test_the_child_points_back_at_the_seed(self, session, journalled):
        journalled(IMPROVES)
        child = next(
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        )
        assert child["parent_id"].endswith(fingerprint(BASELINE))

    def test_the_source_is_stored_once_and_pointed_at(self, session, journalled):
        report = journalled(IMPROVES)
        best = next(
            row
            for row in rows(session, candidates, run_id="h1")
            if row["fingerprint"] == report.best
        )
        body = session.execute(
            sa.select(blobs.c.body).where(blobs.c.hash == best["code_hash"])
        ).scalar()
        assert body == report.program

    def test_a_program_proposed_twice_is_stored_once(self, session, journalled):
        """Content-addressed. A 500-trial run would otherwise store the same
        program hundreds of times."""
        journalled(IMPROVES, IMPROVES, budget=2)
        bodies = session.execute(sa.select(blobs.c.body)).scalars().all()
        assert len(bodies) == len(set(bodies))


class TestTheTrialsAreThere:
    def test_the_trial_is_recorded(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, trials, run_id="h1")) == 1

    def test_it_ends_measured(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["status"] == TrialState.MEASURED

    def test_its_seq_is_the_one_the_tape_used(self, session, journalled):
        journalled(IMPROVES)
        started = next(
            row
            for row in rows(session, events, run_id="h1")
            if row["type"] == "TrialStarted"
        )
        assert rows(session, trials, run_id="h1")[0]["seq"] == started["payload"]["seq"]

    def test_it_remembers_which_candidate_it_started_from(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["parent_fingerprint"] == (
            fingerprint(BASELINE)
        )


class TestATrialThatWasAskedAgain:
    def test_the_retries_are_counted(self, session, journalled):
        journalled(NONSENSE, IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["attempts"] == 1

    def test_a_retry_is_not_a_second_trial(self, session, journalled):
        journalled(NONSENSE, IMPROVES)
        assert len(rows(session, trials, run_id="h1")) == 1

    def test_the_tape_says_it_was_retried_rather_than_rejected(
        self, session, journalled
    ):
        """Two different things that used to be one fact: a retry costs a
        model call, a rejection ends the trial."""
        journalled(NONSENSE, IMPROVES)
        assert "TrialRetried" in [
            row["type"] for row in rows(session, events, run_id="h1")
        ]


class TestATrialThatWasGivenUpOn:
    def test_it_ends_abandoned(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert rows(session, trials, run_id="h1")[0]["status"] == TrialState.ABANDONED

    def test_it_says_why(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert "```python block" in rows(session, trials, run_id="h1")[0]["reason"]

    def test_it_built_no_candidate(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        children = [
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        ]
        assert children == []


class TestWhatEachCandidateScored:
    def test_the_verdict_is_recorded(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, verdicts)) == 1

    def test_it_carries_the_metrics(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, verdicts)[0]["metrics"] == {"value": 45.0}

    def test_it_is_keyed_on_the_candidate_that_was_measured(self, session, journalled):
        report = journalled(IMPROVES)
        assert rows(session, verdicts)[0]["candidate_hash"] == report.best

    def test_it_says_which_task_it_was_measured_against(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, verdicts)[0]["task_hash"]

    def test_it_says_which_seeds_it_was_measured_on(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, verdicts)[0]["seeds_hash"]

    def test_a_failure_is_recorded_with_its_reason_and_no_metrics(
        self, session, journalled
    ):
        journalled(CRASHES)
        row = rows(session, verdicts)[0]
        assert (row["outcome"], row["metrics"]) == (Outcome.CRASHED, None)


class TestTheSameMeasurementTwice:
    def test_measuring_one_program_twice_writes_one_row(self, session, journalled):
        """The key is the measurement, not the attempt. Two trials that
        propose the same program against the same task on the same seeds have
        measured the same thing."""
        journalled(IMPROVES, IMPROVES, budget=2)
        assert len(rows(session, verdicts)) == 1

    def test_two_different_programs_are_two_measurements(self, session, journalled):
        journalled(IMPROVES, IMPROVES_MORE, budget=2)
        assert len(rows(session, verdicts)) == 2


class TestTheCallWeWereAboutToMake:
    """Every other step of a trial happens inside our own process, where
    dying means it either committed or it did not. A model call is the one
    step where dying leaves the question open."""

    def test_the_request_is_written_down(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, model_calls)) == 1

    def test_it_ends_up_marked_done(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, model_calls)[0]["status"] == "done"

    def test_it_keeps_the_recipe_that_rebuilds_the_prompt(self, session, journalled):
        journalled(IMPROVES)
        recipe = rows(session, model_calls)[0]["recipe"]
        assert set(recipe) == {"template", "code", "hint", "guidance"}

    def test_it_counts_what_the_call_cost(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, model_calls)[0]["tokens_out"] > 0

    def test_it_belongs_to_the_trial_that_asked(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, model_calls)[0]["trial_id"] == "h1/0"

    def test_a_retry_is_a_second_call_with_its_own_row(self, session, journalled):
        """Deliberately not the same key: a retry asks the same question
        again, and must not replay the answer that failed to parse."""
        journalled(NONSENSE, IMPROVES)
        assert len(rows(session, model_calls)) == 2

    def test_the_recipe_is_not_also_on_the_tape(self, session, journalled):
        """It holds the whole parent program, and events is the one table
        nobody may prune."""
        journalled(IMPROVES)
        asked = next(
            row
            for row in rows(session, events, run_id="h1")
            if row["type"] == "ModelRequested"
        )
        assert "recipe" not in asked["payload"]


class TestATrialSaysWhatItProduced:
    def test_a_measured_trial_names_its_candidate(self, session, journalled):
        report = journalled(IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["candidate_fingerprint"] == (
            report.best
        )

    def test_an_abandoned_trial_names_nothing(self, session, journalled):
        """It produced no candidate, so there is nothing to point at."""
        journalled(*[NONSENSE] * 4)
        assert rows(session, trials, run_id="h1")[0]["candidate_fingerprint"] is None
