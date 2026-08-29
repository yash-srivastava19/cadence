"""what the model answered

Revision ID: 9c2d5b81a4f3
Revises: 8f1a2c4d6e70
Create Date: 2026-08-29 10:00:00.000000

model_calls recorded that a call was made and what it cost, and not what came
back. Without the answer the table can say "you may already have paid for
this" and cannot do the thing that makes the write-ahead worth its round
trip: hand the answer back instead of buying it twice.

The model column goes with it. A Completion names the model that produced it,
and a replayed one that could not would be a different value than the call it
is replaying.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c2d5b81a4f3"
down_revision: str | Sequence[str] | None = "8f1a2c4d6e70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_calls", sa.Column("model", sa.Text, nullable=True))
    op.add_column("model_calls", sa.Column("latency_ms", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("model_calls", "latency_ms")
    op.drop_column("model_calls", "model")
