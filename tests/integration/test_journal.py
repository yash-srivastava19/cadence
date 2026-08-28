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
from cadence.control.storage import engine, events, runs  # noqa: E402
from cadence.execution.runner import TrialRunner  # noqa: E402
from cadence.execution.sandboxes.subprocess import Subprocess  # noqa: E402
from cadence.lifecycle.states import RunState  # noqa: E402
from cadence.observe.signals import cadence  # noqa: E402
from tests.factories import BASELINE, a_manifest  # noqa: E402

IMPROVES = "Here it is.\n```python\nprint('value: 45')\n```"
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
            "ModelCalled",
            "ProposalReceived",
            "TrialMeasured",
            "RunFinished",
        ]

    def test_the_tape_is_numbered_from_zero(self, session, journalled):
        journalled(IMPROVES)
        assert [row["seq"] for row in rows(session, events, run_id="h1")] == [
            0,
            1,
            2,
            3,
            4,
            5,
        ]

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
