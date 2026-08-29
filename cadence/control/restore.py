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
from pydantic import Field
from sqlalchemy.orm import Session

from cadence.control.storage import blobs, candidates, runs, trials, verdicts
from cadence.core.dto import RunHistory, TrialResult
from cadence.core.values import Value
from cadence.core.verdict import Failed, Outcome, Scored
from cadence.lifecycle.states import CandidateState, RunState, TrialState

__all__ = ["Resumption", "history_of", "resume_from", "seeds_of", "status_of"]


class Resumption(Value):
    """Enough to carry on: what the run has learned, and how far it got.

    Two numbers rather than one, because they count different things. The
    history holds only trials that produced a measured candidate; trials
    counts every trial that started, including the ones that were abandoned.
    Numbering the next trial from the first would reuse a seq the database is
    unique on.
    """

    history: RunHistory
    #: How many trials are settled. The next one takes this as its seq, so an
    #: unfinished trial is redone rather than skipped past.
    trials: int = Field(ge=0)


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
        .where(candidates.c.status != CandidateState.QUARANTINED)
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
        # A quarantined candidate is simply not offered. The search method
        # stays a pure function of what it is handed and never learns that
        # quarantine exists -- which is why it can stay one.
        .where(candidates.c.status != CandidateState.QUARANTINED)
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


#: A trial in one of these is over, whatever it turned out to be.
SETTLED = (TrialState.MEASURED, TrialState.UNUSABLE, TrialState.ABANDONED)


def trials_of(session: Session, run_id: str) -> int:
    """How many trials are over.

    Settled ones only, so the next trial takes the seq of whichever one was
    in flight when the process died. That is what makes the recorded model
    call reachable: the redone trial asks under the same key, and the answer
    it already paid for is handed back instead of bought again.

    A trial redone this way loses whatever it had got to. It is one trial,
    and the alternative -- numbering past it -- leaves a row nothing will
    ever finish and an answer nothing will ever collect.
    """
    return (
        session.execute(
            sa.select(sa.func.count())
            .select_from(trials)
            .where(trials.c.run_id == run_id)
            .where(trials.c.status.in_(SETTLED))
        ).scalar()
        or 0
    )


def resume_from(session: Session, run_id: str) -> Resumption | None:
    """What a run needs to pick up where it stopped, or None if it cannot.

    A run that finished is not resumable: there is nothing left to do and
    starting again under its id would write a second account of it.
    """
    status = status_of(session, run_id)
    if status is None or status in (RunState.FINISHED, RunState.CANCELLED):
        return None
    history = history_of(session, run_id)
    if history is None:
        return None
    return Resumption(history=history, trials=trials_of(session, run_id))
