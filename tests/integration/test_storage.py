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
from cadence.control.storage import engine, runs  # noqa: E402
from cadence.states import RunState  # noqa: E402


# One engine per role for the whole module, disposed at the end. A fresh
# engine per test leaks its pool, and psycopg says so.
@pytest.fixture(scope="module")
def engines():
    made = {"owner": engine(OWNER), "app": engine(APP)}
    yield made
    for one in made.values():
        one.dispose()


@pytest.fixture
def owner(engines):
    with orm.Session(engines["owner"], expire_on_commit=False) as session:
        yield session
        session.rollback()
    with engines["owner"].begin() as connection:
        connection.execute(sa.delete(runs))


@pytest.fixture
def app(engines):
    with orm.Session(engines["app"], expire_on_commit=False) as session:
        yield session
        session.rollback()


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
