"""which question a run belongs to

A shared database needs three levels of identity: which invocation (runs.id),
who (runs.owner, a column that was already here), and which question. This
adds the third.

Not manifest_hash: bumping budget.trials makes a new hash and the same
experiment, so grouping by hash would split a sweep every time somebody
adjusted a knob.

Revision ID: c4e81b90d7a2
Revises: a1f7c93be204
Create Date: 2026-08-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e81b90d7a2"
down_revision: str | Sequence[str] | None = "a1f7c93be204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("experiment", sa.Text(), nullable=True))
    # Partial: an unlabelled run is not a group anybody browses by.
    op.create_index(
        "ix_runs_experiment",
        "runs",
        ["experiment"],
        postgresql_where=sa.text("experiment is not null"),
    )


def downgrade() -> None:
    op.drop_index("ix_runs_experiment", table_name="runs")
    op.drop_column("runs", "experiment")
