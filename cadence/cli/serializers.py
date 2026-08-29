"""Serialize database rows to dicts (shared by CLI and API)."""

from typing import Any


class RunSerializer:
    """Serialize runs."""

    @staticmethod
    def serialize_list(rows: list) -> list[dict]:
        return [RunSerializer.serialize_one(row) for row in rows]

    @staticmethod
    def serialize_one(row: Any) -> dict:
        return {
            "id": row.id,
            "status": row.status,
            "trials": row.trials,
            "best_score": row.best,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "owner": row.owner,
        }


class TrialSerializer:
    """Serialize trials."""

    @staticmethod
    def serialize_list(rows: list) -> list[dict]:
        return [TrialSerializer.serialize_one(row) for row in rows]

    @staticmethod
    def serialize_one(row: Any) -> dict:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "seq": row.seq,
            "status": row.status,
            "attempts": row.attempts,
            "started_at": row.started_at.isoformat() if row.started_at else None,
        }
