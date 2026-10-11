"""which measurement is a trial's own

Verdicts are keyed on (candidate, task, seeds). A trial recorded only its
candidate, so every reader joined on the candidate alone and got one row per
verdict that candidate had. A program measured again -- on fresh seeds by
`pick: confirm`, or under another manifest -- came back as two trials, and a
resumed run handed its search method a history one result longer than the
one it had, which moves every seeded choice after it.

The trial now names the task and seeds it was measured on, and readers join
on all three. Rows already written are filled in from the TrialMeasured event
on the tape, which has always carried both.

Revision ID: d7b2e5a91c40
Revises: c4e81b90d7a2
Create Date: 2026-10-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7b2e5a91c40"
down_revision: str | Sequence[str] | None = "c4e81b90d7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trials", sa.Column("task_hash", sa.String(64), nullable=True))
    op.add_column("trials", sa.Column("seeds_hash", sa.String(64), nullable=True))
    op.execute(
        """
        update trials
           set task_hash = events.payload ->> 'task_hash',
               seeds_hash = events.payload ->> 'seeds_hash'
          from events
         where events.type = 'TrialMeasured'
           and events.payload ->> 'trial_id' = trials.id
        """
    )


def downgrade() -> None:
    op.drop_column("trials", "seeds_hash")
    op.drop_column("trials", "task_hash")
