"""Database queries (shared by CLI and API)."""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cadence.cli.serializers import RunSerializer, TrialSerializer
from cadence.control.storage import runs, trials


class RunQueries:
    """Query runs."""

    @staticmethod
    def list(session: Session, status=None, limit=100):
        """Get all runs."""
        query = sa.select(runs)

        if status:
            query = query.where(runs.c.status == status)

        query = query.order_by(runs.c.started_at.desc()).limit(limit)
        rows = session.execute(query).fetchall()

        return RunSerializer.serialize_list(rows)

    @staticmethod
    def get(session: Session, run_id: str):
        """Get one run."""
        row = session.execute(sa.select(runs).where(runs.c.id == run_id)).first()

        if not row:
            return None

        return RunSerializer.serialize_one(row)


class TrialQueries:
    """Query trials."""

    @staticmethod
    def list(session: Session, run_id: str, status=None, limit=100):
        """Get trials for a run."""
        query = sa.select(trials).where(trials.c.run_id == run_id)

        if status:
            query = query.where(trials.c.status == status)

        query = query.order_by(trials.c.seq.desc()).limit(limit)
        rows = session.execute(query).fetchall()

        return TrialSerializer.serialize_list(rows)

    @staticmethod
    def get(session: Session, trial_id: str):
        """Get one trial."""
        row = session.execute(sa.select(trials).where(trials.c.id == trial_id)).first()

        if not row:
            return None

        return TrialSerializer.serialize_one(row)
