"""Reading runs and trials back for a person to look at.

Separate from restore.py, which reads a run back for the loop to carry on
with. That one rebuilds a RunHistory and joins through blobs to get every
candidate's source; this one answers "what happened, and who did it" and must
stay cheap enough to run against four hundred rows.

Returns DTOs, never strings. What the answer looks like is delivery's job.
"""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cadence.control.storage import candidates, runs, trials, verdicts
from cadence.core.dto import RunSummary, TrialSummary

__all__ = ["one_run", "one_trial", "some_runs", "some_trials"]

#: Enough to browse, few enough that nobody waits. --limit raises it.
PAGE = 50

#: Counted from the trials themselves, not read off runs.trials, which is
#: only written when a run ends. Reading the column would report 0 for every
#: run still going -- and a listing you cannot use on a live run is no use in
#: the terminal next to the one running it.
STARTED = (
    sa.select(sa.func.count())
    .select_from(trials)
    .where(trials.c.run_id == runs.c.id)
    .scalar_subquery()
)


def some_runs(
    session: Session,
    experiment: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    limit: int = PAGE,
) -> list[RunSummary]:
    """Newest first, because the one you want is nearly always the last one."""
    query = (
        sa.select(runs, STARTED.label("started_trials"))
        .order_by(runs.c.started_at.desc())
        .limit(limit)
    )
    for column, wanted in (
        (runs.c.experiment, experiment),
        (runs.c.owner, owner),
        (runs.c.status, status),
    ):
        if wanted is not None:
            query = query.where(column == wanted)
    return [_run(row) for row in session.execute(query).mappings()]


def one_run(session: Session, run_id: str) -> RunSummary | None:
    row = (
        session.execute(
            sa.select(runs, STARTED.label("started_trials")).where(runs.c.id == run_id)
        )
        .mappings()
        .first()
    )
    return None if row is None else _run(row)


#: A trial's score, reached through the candidate it produced.
#:
#: Verdicts are keyed on (candidate, task, seeds) and a trial does not record
#: which task it was, so a candidate scored under two different tasks has two
#: verdicts here and this picks one. restore.py joins the same way for the
#: same reason; a listing is the place where it matters least.
SCORED = trials.outerjoin(
    candidates,
    sa.and_(
        candidates.c.run_id == trials.c.run_id,
        candidates.c.fingerprint == trials.c.candidate_fingerprint,
    ),
).outerjoin(verdicts, verdicts.c.candidate_hash == candidates.c.fingerprint)

TRIAL_COLUMNS = (trials, verdicts.c.outcome, verdicts.c.metrics)


def some_trials(
    session: Session,
    run_id: str,
    status: str | None = None,
    limit: int = PAGE,
) -> list[TrialSummary]:
    """In the order they were tried. A trial only means anything next to the
    one before it."""
    query = (
        sa.select(*TRIAL_COLUMNS)
        .select_from(SCORED)
        .where(trials.c.run_id == run_id)
        .order_by(trials.c.seq)
        .limit(limit)
    )
    if status is not None:
        query = query.where(trials.c.status == status)
    return [_trial(row) for row in session.execute(query).mappings()]


def one_trial(session: Session, trial_id: str) -> TrialSummary | None:
    row = (
        session.execute(
            sa.select(*TRIAL_COLUMNS).select_from(SCORED).where(trials.c.id == trial_id)
        )
        .mappings()
        .first()
    )
    return None if row is None else _trial(row)


def _run(row) -> RunSummary:
    return RunSummary(
        id=row["id"],
        status=row["status"],
        trials=row["started_trials"],
        owner=row["owner"],
        experiment=row["experiment"],
        best=row["best"],
        reason=row["reason"],
        started_at=row["started_at"],
    )


def _trial(row) -> TrialSummary:
    return TrialSummary(
        id=row["id"],
        run_id=row["run_id"],
        seq=row["seq"],
        status=row["status"],
        attempts=row["attempts"],
        parent=row["parent_fingerprint"],
        candidate=row["candidate_fingerprint"],
        outcome=row["outcome"],
        metrics=row["metrics"],
        reason=row["reason"],
        started_at=row["started_at"],
    )
