"""two tables nothing wrote to

Both were designed before the code that would fill them, and the code that
arrived put the fact somewhere else.

quarantine: a candidate that keeps crashing is already retired durably --
journal counts the crashes on candidates.crashes and moves the row to
QUARANTINED, and restore refuses to offer it back. The table held the same
fact keyed on fingerprint alone, which is also the wrong key for it: whether a
program crashes depends on the verifier, the limits and the seeds, which is
exactly why verdicts is keyed on (candidate, task, seeds) rather than on the
code. Quarantine that outlives one run is a real feature and a different one:
it needs the task in its key, an expiry, and a decision about why a ban should
survive the experiment that earned it.

idempotency_keys: the write-ahead claim for a model call already lives on
model_calls, which is written in_flight before the call and done after it, and
which recall reads back. This table is shaped for an API cadence serves --
scope, response_body, response_code -- not for the calls it makes.

Neither is a deletion of an idea. A key that does nothing is a promise, and
the schema should say what the code does.

Revision ID: a1f7c93be204
Revises: 9c2d5b81a4f3
Create Date: 2026-08-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations.grants import ADVANCES, SWEEPABLE, grant

# revision identifiers, used by Alembic.
revision: str = "a1f7c93be204"
down_revision: str | Sequence[str] | None = "9c2d5b81a4f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("quarantine")
    # Dropping this one takes the only DELETE grant in the database with it,
    # which is the point: nothing is sweepable any more, so nothing may erase.
    op.drop_table("idempotency_keys")


def downgrade() -> None:
    op.create_table(
        "quarantine",
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("crashes", sa.Integer(), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("fingerprint"),
        comment="Read at dispatch. A poison candidate surviving restart loops forever.",
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('in_flight', 'done')", name="idempotency_status"
        ),
        sa.PrimaryKeyConstraint("key"),
        comment="The one table a sweeper deletes from, hence the DELETE grant.",
    )
    # Restored with the grants they had, or downgrading would leave two tables
    # the application cannot read.
    grant("quarantine", ADVANCES)
    grant("idempotency_keys", SWEEPABLE)
