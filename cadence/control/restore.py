"""Reading a run back out of the database.

The mirror of journal.py, and deliberately not part of it: writing happens a
fact at a time as a run proceeds, reading happens once when one is picked up
again, and the two have no code in common worth sharing.

What comes back is a RunHistory -- the same thing the loop builds in memory
today, assembled from rows instead. That is the whole point of the shape: a
search method takes a RunHistory and cannot tell where it came from, so
nothing about the method changes when the answer starts coming from Postgres.
"""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cadence.control.storage import blobs, candidates, runs, trials, verdicts
from cadence.core.dto import RunHistory, TrialResult
from cadence.core.verdict import Failed, Outcome, Scored
from cadence.lifecycle.states import TrialState

__all__ = ["history_of", "seeds_of", "status_of"]


def status_of(session: Session, run_id: str) -> str | None:
    """What the database last knew about this run, or None if it has none."""
    return session.execute(sa.select(runs.c.status).where(runs.c.id == run_id)).scalar()


def seeds_of(session: Session, run_id: str) -> tuple[str, ...]:
    """The programs the run started from.

    They are the candidates with no parent -- everything else descends from
    one of them.
    """
    rows = session.execute(
        sa.select(blobs.c.body)
        .select_from(candidates.join(blobs, candidates.c.code_hash == blobs.c.hash))
        .where(candidates.c.run_id == run_id)
        .where(candidates.c.parent_id.is_(None))
        .order_by(candidates.c.created_at, candidates.c.fingerprint)
    ).scalars()
    return tuple(rows)


def history_of(session: Session, run_id: str) -> RunHistory | None:
    """Everything a search method needs to carry on where this run left off.

    Only measured trials are in it. A trial that was abandoned or whose patch
    would not apply produced no candidate and therefore no result, which is
    the same thing the in-memory loop does with one.
    """
    seeds = seeds_of(session, run_id)
    if not seeds:
        return None
    return RunHistory(
        run_id=run_id, seeds=seeds, results=tuple(_results(session, run_id))
    )


def _results(session: Session, run_id: str) -> list[TrialResult]:
    measured = (
        trials.join(
            candidates,
            sa.and_(
                candidates.c.run_id == trials.c.run_id,
                candidates.c.fingerprint == trials.c.candidate_fingerprint,
            ),
        )
        .join(blobs, candidates.c.code_hash == blobs.c.hash)
        .join(verdicts, verdicts.c.candidate_hash == candidates.c.fingerprint)
    )
    rows = session.execute(
        sa.select(
            blobs.c.body,
            candidates.c.fingerprint,
            verdicts.c.outcome,
            verdicts.c.metrics,
            verdicts.c.reason,
        )
        .select_from(measured)
        .where(trials.c.run_id == run_id)
        .where(trials.c.status == TrialState.MEASURED)
        # In the order they were tried. A method that walks the history is
        # entitled to see it happen the way it happened.
        .order_by(trials.c.seq)
    ).mappings()
    return [TrialResult(code=row["body"], verdict=_verdict(row)) for row in rows]


def _verdict(row) -> Scored | Failed:
    if row["outcome"] == Outcome.SCORED:
        return Scored(fingerprint=row["fingerprint"], metrics=row["metrics"])
    return Failed(
        fingerprint=row["fingerprint"],
        outcome=row["outcome"],
        reason=row["reason"],
    )
