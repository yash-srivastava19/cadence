"""The door to the database, and what it refuses.

No postgres here on purpose: what these test is the guard and the translation,
and both are decisions cadence makes before any row is written. The rows
themselves are tests/integration/test_storage.py's problem.
"""

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import OperationalError

from cadence.control.storage import (
    EXPECTED_REVISION,
    demand_current_schema,
    revision_of,
    translating,
)
from cadence.errors import CadenceError, SchemaOutOfDate, StorageError
from cadence.observe.channel import Fact


def a_database(revision=None):
    """An empty database, optionally stamped as alembic would stamp it."""
    made = sa.create_engine("sqlite://")
    if revision is not None:
        with made.begin() as connection:
            connection.execute(
                sa.text("create table alembic_version (version_num text)")
            )
            connection.execute(
                sa.text("insert into alembic_version values (:r)"), {"r": revision}
            )
    return made


class TestTheExpectedRevisionCannotDrift:
    def test_it_is_the_head_alembic_would_upgrade_to(self):
        """The constant is what the running code checks; the migrations are
        what actually build the schema. Nothing else keeps the two the same,
        so a migration added without touching the constant fails here rather
        than at somebody's first run."""
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        assert head == EXPECTED_REVISION


class TestADatabaseIsCheckedBeforeItIsUsed:
    def test_one_at_the_expected_revision_is_accepted(self):
        demand_current_schema(a_database(EXPECTED_REVISION))

    def test_an_empty_one_is_refused(self):
        with pytest.raises(SchemaOutOfDate):
            demand_current_schema(a_database())

    def test_it_says_how_to_fix_an_empty_one(self):
        with pytest.raises(SchemaOutOfDate, match="alembic upgrade head"):
            demand_current_schema(a_database())

    def test_it_offers_the_other_way_out_of_an_empty_one(self):
        """Recording is optional. A user who wanted a run, not an audit
        trail, should not have to run a migration to get one."""
        with pytest.raises(SchemaOutOfDate, match="unset DATABASE_URL"):
            demand_current_schema(a_database())

    def test_one_at_the_wrong_revision_is_refused(self):
        with pytest.raises(SchemaOutOfDate):
            demand_current_schema(a_database("0000deadbeef"))

    def test_it_names_both_revisions(self):
        """Which one it is and which one it needs. Either alone leaves the
        reader guessing whether they are ahead or behind."""
        with pytest.raises(SchemaOutOfDate) as raised:
            demand_current_schema(a_database("0000deadbeef"))
        assert "0000deadbeef" in str(raised.value)
        assert EXPECTED_REVISION in str(raised.value)

    def test_a_database_with_no_alembic_version_reports_none(self):
        with a_database().connect() as connection:
            assert revision_of(connection) is None

    def test_a_stamped_one_reports_its_revision(self):
        with a_database("0000deadbeef").connect() as connection:
            assert revision_of(connection) == "0000deadbeef"


class TestALostWriteStopsTheRun:
    """The journal runs as a subscriber, so a driver error raised inside it
    unwinds through whichever line of the loop published the fact -- nowhere
    near a handler. It has to leave as a StorageError or it reaches the user
    as a traceback."""

    def _journal(self, session):
        from cadence.control.journal import Journal

        return Journal(session)

    def test_a_failed_write_leaves_as_a_storage_error(self):
        with pytest.raises(StorageError):
            self._journal(Refusing()).record(a_run_started())

    def test_the_transaction_is_rolled_back(self):
        """A failed transaction nobody rolls back poisons every write after
        it, so the second failure would be about the first one."""
        session = Refusing()
        with pytest.raises(StorageError):
            self._journal(session).record(a_run_started())
        assert session.rolled_back

    def test_a_fact_about_no_run_is_not_a_write(self):
        assert self._journal(Refusing()).record(NotAboutARun()) is None


class Refusing:
    """A session that cannot write, the way an unreachable database cannot."""

    def __init__(self):
        self.rolled_back = False

    def execute(self, *args, **kwargs):
        raise OperationalError("insert into runs", {}, Exception("no route"))

    def commit(self):
        raise AssertionError("should not have got as far as committing")

    def rollback(self):
        self.rolled_back = True


class NotAboutARun(Fact):
    """A fact with no run_id. The channel carries them; the journal ignores
    them, because there is nothing to write one against."""


def a_run_started():
    from cadence.core.dto import RecordedManifest
    from cadence.observe.signals import RunStarted

    return RunStarted(
        run_id="h1",
        method="Evolution",
        manifest=RecordedManifest(
            hash="f" * 16, source="program: p.py", api_version="cadence/v1alpha2"
        ),
        seeds=("print(1)",),
        budget={"trials": 1.0},
    )


class TestTheDriverDoesNotEscape:
    """Rule 5: a failure crosses a plane boundary as a value. Above this line
    nothing knows psycopg exists, so nothing above it can be asked to catch a
    psycopg exception."""

    def test_a_driver_error_leaves_as_a_storage_error(self):
        with pytest.raises(StorageError), translating():
            raise OperationalError("select 1", {}, Exception("no route"))

    def test_which_the_command_already_catches(self):
        assert issubclass(StorageError, CadenceError)

    def test_it_keeps_the_sentence_about_the_database(self):
        with pytest.raises(StorageError, match="no route"), translating():
            raise OperationalError("select 1", {}, Exception("no route"))

    def test_it_drops_the_sql_that_produced_it(self):
        """psycopg stringifies to the statement and its parameters as well,
        which is a wall of text about our query when what the user needs is
        the one line about their database."""
        with pytest.raises(StorageError) as raised, translating():
            raise OperationalError(
                "insert into runs values (1)", {}, Exception("no route")
            )
        assert "insert into runs" not in str(raised.value)

    def test_the_original_is_still_attached(self):
        with pytest.raises(StorageError) as raised, translating():
            raise OperationalError("select 1", {}, Exception("no route"))
        assert isinstance(raised.value.__cause__, OperationalError)

    def test_anything_else_passes_through_untouched(self):
        """Only the driver is translated. A bug in cadence is not a storage
        failure, and dressing one up as the other hides it."""
        with pytest.raises(ZeroDivisionError), translating():
            raise ZeroDivisionError("a bug in cadence, not in the database")
