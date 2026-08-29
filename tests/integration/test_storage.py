import os
from pathlib import Path

import pytest

OWNER = os.environ.get("TEST_DATABASE_URL")
APP = os.environ.get("TEST_DATABASE_APP_URL")

if not (OWNER and APP):
    pytest.skip(
        "needs TEST_DATABASE_URL and TEST_DATABASE_APP_URL; run 'docker compose up -d'",
        allow_module_level=True,
    )

sa = pytest.importorskip("sqlalchemy", reason="run 'pip install -e .'")

from sqlalchemy import orm  # noqa: E402
from sqlalchemy.exc import ProgrammingError  # noqa: E402
from statemachine.exceptions import TransitionNotAllowed  # noqa: E402

from cadence.control.entities import Run  # noqa: E402
from cadence.control.storage import (  # noqa: E402
    blobs,
    budget,
    candidates,
    engine,
    events,
    manifests,
    metadata,
    model_calls,
    runs,
    templates,
    trials,
    verdicts,
)
from cadence.lifecycle.states import RunState  # noqa: E402

# What the migration granted, and what a reviewer can read off `\dp` in psql.
APPEND_ONLY = (blobs, manifests, templates, verdicts, events, model_calls)
ADVANCES = (runs, trials, candidates, budget)


# One engine per role for the whole module, disposed at the end. A fresh
# engine per test leaks its pool, and psycopg says so.
@pytest.fixture(scope="module")
def engines():
    made = {"owner": engine(OWNER), "app": engine(APP)}
    yield made
    for one in made.values():
        one.dispose()


def _in_a_transaction_that_is_rolled_back(engine):
    """Rails' transactional fixtures, in SQLAlchemy.

    The session is bound to a connection that is already inside a
    transaction, and join_transaction_mode="create_savepoint" makes the
    session's own commits into SAVEPOINTs. So code under test may commit
    freely, and rolling back the outer transaction still reverts everything.

    This is what lets an end-to-end spec run the real loop -- which commits --
    without leaving rows behind, and it replaces deleting from each table by
    hand, which does not scale past one.
    """
    connection = engine.connect()
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
def owner(engines):
    yield from _in_a_transaction_that_is_rolled_back(engines["owner"])


@pytest.fixture
def app(engines):
    yield from _in_a_transaction_that_is_rolled_back(engines["app"])


class TestARunSurvivesARestart:
    def test_it_can_be_saved(self, owner):
        owner.add(Run(id="r1"))
        owner.commit()
        assert owner.get(Run, "r1") is not None

    def test_it_comes_back_in_the_state_it_was_left(self, owner):
        run = Run(id="r1")
        run.start()
        owner.add(run)
        owner.commit()
        owner.expunge_all()
        assert owner.get(Run, "r1").status == RunState.RUNNING

    def test_a_loaded_run_can_still_transition(self, owner):
        run = Run(id="r1")
        run.start()
        owner.add(run)
        owner.commit()
        owner.expunge_all()

        reloaded = owner.get(Run, "r1")
        reloaded.finish(best="abc123")
        owner.commit()
        assert reloaded.status == RunState.FINISHED

    def test_a_loaded_run_knows_what_it_may_not_do(self, owner):
        run = Run(id="r1")
        run.start()
        run.finish()
        owner.add(run)
        owner.commit()
        owner.expunge_all()

        reloaded = owner.get(Run, "r1")
        assert reloaded.is_final
        assert not reloaded.may_start

    def test_a_guard_still_applies_after_a_reload(self, owner):
        run = Run(id="r1")
        run.start()
        owner.add(run)
        owner.commit()
        owner.expunge_all()

        reloaded = owner.get(Run, "r1")
        with pytest.raises(TransitionNotAllowed):
            reloaded.fail(reason="")

    def test_the_column_holds_the_value_not_the_member_name(self, owner):
        run = Run(id="r1")
        run.start()
        owner.add(run)
        owner.commit()
        stored = owner.execute(sa.select(runs.c.status)).scalar()
        assert stored == "running"


class TestTheEntityStaysPlain:
    def test_entities_import_no_orm(self):
        import cadence.control.entities as entities

        assert "sqlalchemy" not in entities.__dict__
        source = Path(entities.__file__).read_text()
        assert "sqlalchemy" not in source


class TestWhatTheApplicationRoleMayDo:
    def test_it_can_record_a_run(self, owner, app):
        app.add(Run(id="r1"))
        app.commit()
        assert app.get(Run, "r1") is not None

    def test_it_can_advance_a_run(self, owner, app):
        run = Run(id="r1")
        app.add(run)
        app.commit()
        run.start()
        app.commit()
        assert app.get(Run, "r1").status == RunState.RUNNING

    def test_it_cannot_erase_a_run(self, owner, app):
        app.add(Run(id="r1"))
        app.commit()
        with pytest.raises(ProgrammingError):
            app.execute(sa.delete(runs))


def _as_app(table, statement):
    """Run one statement as the restricted role, in its own connection."""
    with (
        engine(APP).connect() as connection,
        pytest.raises(ProgrammingError, match="permission denied"),
    ):
        connection.execute(statement)


class TestTheLedgerCannotBeRewritten:
    """The reason this project needs Postgres rather than SQLite.

    SQLite has no GRANT, so "the log can never be edited" would be a habit.
    Here it is a property of the database, and these tests are what keep it
    one as tables are added.
    """

    @pytest.mark.parametrize("table", APPEND_ONLY, ids=lambda t: t.name)
    def test_an_append_only_table_cannot_be_updated(self, table):
        column = next(iter(table.c))
        _as_app(table, sa.update(table).values({column: column}))

    @pytest.mark.parametrize("table", APPEND_ONLY, ids=lambda t: t.name)
    def test_an_append_only_table_cannot_be_deleted_from(self, table):
        _as_app(table, sa.delete(table))

    @pytest.mark.parametrize("table", ADVANCES, ids=lambda t: t.name)
    def test_a_table_that_advances_cannot_be_deleted_from(self, table):
        _as_app(table, sa.delete(table))


class TestNothingMayErase:
    """There is no sweepable table any more.

    idempotency_keys was the only one the application could delete from, and
    it held a claim that already lives on model_calls. With it gone the rule
    has no exception: every table the application can reach refuses DELETE,
    which is a stronger sentence than the one it replaces.
    """

    def test_no_table_grants_delete_to_the_application(self):
        # cadence's own tables. alembic_version is not one of them: it is
        # alembic's, written by the owner, and it inherits the database's
        # default privileges rather than a migration's grant.
        with engine(OWNER).connect() as connection:
            granted = connection.execute(
                sa.text(
                    "select table_name from information_schema.role_table_grants"
                    " where grantee = 'cadence_app' and privilege_type = 'DELETE'"
                    " and table_name = any(:names)"
                ),
                {"names": sorted(metadata.tables)},
            ).scalars()
        assert list(granted) == []
