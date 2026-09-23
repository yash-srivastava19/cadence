"""`cadence db` against a real Postgres, on a database of its own.

A scratch database rather than TEST_DATABASE_URL itself: these tests migrate
to base and back, and the other integration tests expect their schema to be
there.
"""

import os
from collections.abc import Iterator

import pytest
import sqlalchemy as sa

from cadence.control import schema
from cadence.control.storage import dsn, engine
from cadence.migrations import grants

SCRATCH = "cadence_db_commands_test"


def _url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    _url() is None, reason="needs TEST_DATABASE_URL; run 'docker compose up -d'"
)


@pytest.fixture
def scratch() -> Iterator[str]:
    """An empty database, dropped afterwards."""
    admin = sa.engine.make_url(dsn(_url())).set(database="postgres")
    bound = sa.create_engine(admin, isolation_level="AUTOCOMMIT")
    with bound.connect() as connection:
        connection.execute(sa.text(f'drop database if exists "{SCRATCH}"'))
        connection.execute(sa.text(f'create database "{SCRATCH}"'))
    bound.dispose()
    # render_as_string, not str(): str() masks the password as ***.
    scratch = sa.engine.make_url(_url()).set(database=SCRATCH)
    yield scratch.render_as_string(hide_password=False)
    bound = sa.create_engine(admin, isolation_level="AUTOCOMMIT")
    with bound.connect() as connection:
        connection.execute(sa.text(f'drop database if exists "{SCRATCH}"'))
    bound.dispose()


def test_an_empty_database_is_not_current(scratch: str) -> None:
    state = schema.state(scratch)

    assert state.at is None
    assert not state.is_current
    assert state.pending, "an empty database has every migration to apply"
    assert state.where.endswith(f"/{SCRATCH}"), "it says which database it read"


def test_upgrade_brings_it_to_what_this_cadence_writes(scratch: str) -> None:
    schema.upgrade(scratch)

    state = schema.state(scratch)
    assert state.is_current
    assert state.at == state.expected
    assert not state.pending


def test_upgrade_only_touches_the_database_it_was_given(scratch: str) -> None:
    """--url, not DATABASE_URL: env.py used to read the environment regardless."""
    os.environ["DATABASE_URL"] = "postgresql://nobody@127.0.0.1:1/not-a-database"
    try:
        schema.upgrade(scratch)
    finally:
        del os.environ["DATABASE_URL"]

    assert schema.state(scratch).is_current


def test_rollback_to_base_leaves_nothing_of_cadence(scratch: str) -> None:
    schema.upgrade(scratch)

    schema.downgrade(scratch, "base")

    bound = engine(scratch)
    with bound.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names())
    bound.dispose()
    assert "runs" not in tables
    assert schema.state(scratch).at is None


def test_a_database_without_the_app_role_still_migrates(
    scratch: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grants are hardening for a shared database, not a requirement."""
    monkeypatch.setattr(grants, "APP", "a_role_this_cluster_does_not_have")

    schema.upgrade(scratch)

    assert schema.state(scratch).is_current
