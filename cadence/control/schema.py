"""The database schema: where the migrations are, and what state one is in.

The migrations ship inside the package, so a cadence installed with `uv tool
install` can create its own schema. Nothing here reaches for alembic.ini:
that file is for contributors running alembic by hand from a checkout, and
both paths run the same migration scripts.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from cadence.control.storage import (
    APP_ROLE,
    EXPECTED_REVISION,
    connecting,
    dsn,
    engine,
    revision_of,
    translating,
)
from cadence.core.dto import SchemaState

__all__ = ["MIGRATIONS", "config", "downgrade", "state", "upgrade"]

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", dsn(url))
    return cfg


def where(url: str) -> str:
    made = sa.engine.make_url(dsn(url))
    return f"{made.host or 'local'}:{made.port or 5432}/{made.database}"


def state(url: str) -> SchemaState:
    scripts = ScriptDirectory.from_config(config(url))
    head = scripts.get_current_head() or ""
    bound = engine(url)
    try:
        with translating(), connecting(bound) as connection:
            at = revision_of(connection)
            role = connection.execute(
                sa.text("select 1 from pg_roles where rolname = :name"),
                {"name": APP_ROLE},
            ).scalar()
            pending = tuple(
                script.revision
                for script in scripts.iterate_revisions(head, at or "base")
            )
    finally:
        bound.dispose()
    return SchemaState(
        where=where(url),
        at=at,
        head=head,
        expected=EXPECTED_REVISION,
        pending=tuple(reversed(pending)),
        app_role=bool(role),
    )


def upgrade(url: str, to: str = "head") -> None:
    with translating():
        command.upgrade(config(url), to)


def downgrade(url: str, to: str) -> None:
    with translating():
        command.downgrade(config(url), to)
