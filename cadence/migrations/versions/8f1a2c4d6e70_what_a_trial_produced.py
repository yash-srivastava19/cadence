"""what a trial produced

Revision ID: 8f1a2c4d6e70
Revises: 421343018093
Create Date: 2026-08-29 09:00:00.000000

trials recorded what a trial started from and never what it made. The link
existed only inside a CandidateBuilt payload on the tape, and answering
"which candidate did this trial produce" by parsing an append-only log is the
kind of thing that works until someone reshapes a payload.

Nullable, because a trial that was abandoned or whose patch would not apply
never produced one -- and because the trials already in the database were
written before this column existed.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f1a2c4d6e70"
down_revision: str | Sequence[str] | None = "421343018093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trials",
        sa.Column("candidate_fingerprint", sa.String(64), nullable=True),
    )
    # No foreign key to candidates.id: the candidate row is written by the
    # same fact that fills this in, and a constraint between two writes of one
    # statement buys nothing that the write order does not already give.
    op.create_index(
        "trials_candidate_fingerprint",
        "trials",
        ["run_id", "candidate_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("trials_candidate_fingerprint", table_name="trials")
    op.drop_column("trials", "candidate_fingerprint")
