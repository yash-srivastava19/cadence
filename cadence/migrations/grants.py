"""What the application role may do to each table.

Autogenerate never writes grants, so this is the one part of every migration
that is entirely hand-written -- and the part that carries the invariant.

The letters match what ``\\dp`` prints in psql, so the migration, the database
and the person reading either one all use the same vocabulary.
"""

import sqlalchemy as sa
from alembic import op

from cadence.control.storage import APP_ROLE as APP

LETTERS = {"a": "INSERT", "r": "SELECT", "w": "UPDATE", "d": "DELETE"}

APPEND_ONLY = "ar"
"""Content-addressed or historical. A row can never legitimately change."""

ADVANCES = "arw"
"""Carries a status that moves forward. Never erased."""

SWEEPABLE = "arwd"
"""Rows expire on a TTL, so something has to delete them.

No table carries this today: idempotency_keys was the only one and it is
dropped in a1f7c93be204. Kept because the migration that granted it still
imports it -- a migration is history, and history has to keep running.
"""


def exists() -> bool:
    """Whether the application role is there to grant anything to.

    A shared database has one and the grants are the invariant. A researcher's
    own Postgres usually has only its owner, and a migration that failed on a
    missing role would be a migration nobody outside this repo could run.
    """
    return bool(
        op.get_bind()
        .execute(sa.text("select 1 from pg_roles where rolname = :name"), {"name": APP})
        .scalar()
    )


def grant(table: str, letters: str) -> None:
    if not exists():
        return
    allowed = [LETTERS[letter] for letter in letters]
    denied = [name for letter, name in LETTERS.items() if letter not in letters]
    op.execute(f"GRANT {', '.join(allowed)} ON {table} TO {APP}")
    if denied:
        op.execute(f"REVOKE {', '.join(denied)} ON {table} FROM {APP}")
