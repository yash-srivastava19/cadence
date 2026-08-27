"""runs

Revision ID: 2b605efc34c7
Revises:
Create Date: 2026-08-23 08:28:10.166836

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b605efc34c7"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


APP = "cadence_app"


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "paused",
                "finished",
                "cancelled",
                "failed",
                name="run_state",
            ),
            nullable=False,
        ),
        sa.Column("trials", sa.Integer(), server_default="0", nullable=False),
        sa.Column("best", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # A run's status changes as it progresses, so the application may UPDATE.
    # It may never DELETE: a finished run is history.
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON runs TO {APP}")
    op.execute(f"REVOKE DELETE ON runs FROM {APP}")


def downgrade() -> None:
    op.drop_table("runs")
    # drop_table leaves the enum type behind; a re-upgrade would then fail.
    sa.Enum(name="run_state").drop(op.get_bind())
