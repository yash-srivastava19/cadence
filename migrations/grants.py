"""What the application role may do to each table.

Autogenerate never writes grants, so this is the one part of every migration
that is entirely hand-written -- and the part that carries the invariant.

The letters match what ``\\dp`` prints in psql, so the migration, the database
and the person reading either one all use the same vocabulary.
"""

from alembic import op

APP = "cadence_app"

LETTERS = {"a": "INSERT", "r": "SELECT", "w": "UPDATE", "d": "DELETE"}

APPEND_ONLY = "ar"
"""Content-addressed or historical. A row can never legitimately change."""

ADVANCES = "arw"
"""Carries a status that moves forward. Never erased."""

SWEEPABLE = "arwd"
"""Rows expire on a TTL, so something has to delete them."""


def grant(table: str, letters: str) -> None:
    allowed = [LETTERS[letter] for letter in letters]
    denied = [name for letter, name in LETTERS.items() if letter not in letters]
    op.execute(f"GRANT {', '.join(allowed)} ON {table} TO {APP}")
    if denied:
        op.execute(f"REVOKE {', '.join(denied)} ON {table} FROM {APP}")
