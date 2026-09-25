"""Reading runs and trials back for a person to look at.

Separate from restore.py, which reads a run back for the loop to carry on
with. That one rebuilds a RunHistory and joins through blobs to get every
candidate's source; this one answers "what happened, and who did it" and must
stay cheap enough to run against four hundred rows.

Returns DTOs, never strings. What the answer looks like is delivery's job.
"""

import difflib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
import yaml
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session

from cadence.control.storage import (
    blobs,
    candidates,
    events,
    manifests,
    model_calls,
    runs,
    trials,
    verdicts,
)
from cadence.core.dto import (
    ExperimentSummary,
    RunDetail,
    RunSummary,
    Spend,
    TrialDetail,
    TrialSummary,
)
from cadence.core.verdict import Outcome
from cadence.lifecycle.states import RunState

__all__ = [
    "one_run",
    "one_trial",
    "run_detail",
    "some_experiments",
    "some_runs",
    "some_trials",
    "trial_detail",
]

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

#: When this run last wrote anything down.
#:
#: A run's process can be killed -- Ctrl-C, an OOM, a laptop closing -- and
#: nothing writes a terminal status, so the row says RUNNING forever. There
#: were four such rows from a week earlier when this was written.
#:
#: The tape is the heartbeat. Every fact with a run id is appended to events,
#: and ModelRequested is written *before* the call rather than after, so even
#: a run stuck waiting on a slow provider has touched this recently.
HEARTBEAT = (
    sa.select(sa.func.max(events.c.recorded_at))
    .where(events.c.run_id == runs.c.id)
    .scalar_subquery()
)

#: How quiet a running run has to be before the listing stops believing it.
#:
# ponytail: one constant, not a per-manifest setting. It has to clear one
# model call plus one scoring pass; raise it if somebody's verifier is slower
# than this, and make it configurable only once somebody actually needs it.
SILENT_FOR = timedelta(minutes=15)


def some_runs(
    session: Session,
    experiment: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    limit: int = PAGE,
) -> list[RunSummary]:
    """Newest first, because the one you want is nearly always the last one."""
    query = (
        sa.select(runs, STARTED.label("started_trials"), HEARTBEAT.label("last_wrote"))
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
            sa.select(
                runs, STARTED.label("started_trials"), HEARTBEAT.label("last_wrote")
            ).where(runs.c.id == run_id)
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


def _stalled(status: str, last_wrote: datetime | None) -> bool:
    """Says RUNNING, has not written anything in a long time.

    Reported rather than stored: a listing that computes this needs no column,
    no migration and no writer, and a run that comes back to life stops being
    stalled by itself.
    """
    if status != RunState.RUNNING or last_wrote is None:
        return False
    if last_wrote.tzinfo is None:
        last_wrote = last_wrote.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_wrote > SILENT_FOR


def _run(row) -> RunSummary:
    return RunSummary(
        id=row["id"],
        status=row["status"],
        stalled=_stalled(row["status"], row["last_wrote"]),
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


# --- one page's worth: the joins a fifty-row listing will not pay for ------


#: The work a run asked for, replays included. Off the tape, because the
#: tape is the only place that says which calls were replays: `ModelCalled`
#: carries `replayed`, and a replayed answer read back out of the database
#: never became a model_calls row of its own.
#:
#: Spend says what these two numbers mean and they have to keep meaning it:
#: `calls` and `tokens` are what it takes to reproduce the run, so a replay
#: counts. A Report built by the loop and a RunDetail built by this query
#: are about the same run, and the page would print whichever disagreed.
def _said(field: str):
    return sa.cast(events.c.payload[field].astext, sa.Integer)


WORKED = (
    sa.select(
        events.c.run_id,
        sa.func.count().label("calls"),
        sa.func.count()
        .filter(events.c.payload["replayed"].astext == "true")
        .label("replayed"),
        sa.func.coalesce(sa.func.sum(_said("tokens_in")), 0).label("tokens_in"),
        sa.func.coalesce(sa.func.sum(_said("tokens_out")), 0).label("tokens_out"),
    )
    .where(events.c.type == "ModelCalled")
    .group_by(events.c.run_id)
    .subquery()
)

#: And the bill, which is the other half of Spend and counts differently:
#: replays excluded, because an answer read back out of the database was not
#: bought again. The price is not on the tape -- only model_calls records it
#: -- and a replay never gets a row here, so this is already replay-free.
BILLED = (
    sa.select(
        model_calls.c.run_id,
        sa.func.sum(model_calls.c.cost_usd).label("usd"),
    )
    .where(model_calls.c.status == "done")
    .group_by(model_calls.c.run_id)
    .subquery()
)

#: The first fact this run wrote. runs.started_at is set when the row is
#: inserted and the tape starts at the same moment, but a resumed run keeps
#: its original started_at -- so the pair below measures elapsed wall time,
#: not time spent working, and the run page says so.
FIRST_WROTE = (
    sa.select(sa.func.min(events.c.recorded_at))
    .where(events.c.run_id == runs.c.id)
    .scalar_subquery()
)

#: How many of this run's trials came back with a score. The rest crashed,
#: timed out, or never produced a candidate at all.
SCORED_TRIALS = (
    sa.select(sa.func.count())
    .select_from(SCORED)
    .where(sa.and_(trials.c.run_id == runs.c.id, verdicts.c.outcome == Outcome.SCORED))
    .scalar_subquery()
)


# What the seed scored, before the search touched anything.
#
# Off the tape, not through candidates: a seed candidate's fingerprint and the
# fingerprint its verdict is keyed on are different values, so that join never
# matches. SeedMeasured carries the verdict itself.
BASELINE = (
    sa.select(events.c.payload["verdict"]["metrics"])
    .where(
        sa.and_(
            events.c.run_id == runs.c.id,
            events.c.type == "SeedMeasured",
            events.c.payload["verdict"]["outcome"].astext == Outcome.SCORED.value,
        )
    )
    .order_by(events.c.seq)
    .limit(1)
    .scalar_subquery()
)


def _declared(manifest: str | None) -> tuple[Mapping[str, str], int | None]:
    """Which way is better, and how many trials were allowed.

    Read here rather than on every surface that shows a number, so the CLI and
    the browser cannot disagree about which direction a metric improves in. A
    manifest that will not parse is not an error worth failing a page over:
    the run still happened, and the page renders without the direction.
    """
    if not manifest:
        return {}, None
    try:
        document = yaml.safe_load(manifest) or {}
    except yaml.YAMLError:
        return {}, None
    if not isinstance(document, dict):
        return {}, None
    metrics = document.get("metrics")
    budget = document.get("budget")
    directions = {
        str(name): str(way)
        for name, way in (metrics or {}).items()
        if isinstance(metrics, dict)
    }
    trials = (budget or {}).get("trials") if isinstance(budget, dict) else None
    return directions, trials if isinstance(trials, int) else None


def run_detail(session: Session, run_id: str) -> RunDetail | None:
    """One run, with what it spent and what it was started from."""
    row = (
        session.execute(
            sa.select(
                runs,
                STARTED.label("started_trials"),
                HEARTBEAT.label("last_wrote"),
                FIRST_WROTE.label("first_wrote"),
                SCORED_TRIALS.label("scored"),
                WORKED.c.calls,
                WORKED.c.replayed,
                WORKED.c.tokens_in,
                WORKED.c.tokens_out,
                BILLED.c.usd,
                manifests.c.source.label("manifest"),
                BASELINE.label("baseline"),
            )
            .select_from(
                runs.outerjoin(WORKED, WORKED.c.run_id == runs.c.id)
                .outerjoin(BILLED, BILLED.c.run_id == runs.c.id)
                .outerjoin(manifests, manifests.c.hash == runs.c.manifest_hash)
            )
            .where(runs.c.id == run_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    directions, cap_trials = _declared(row["manifest"])
    return RunDetail(
        **_run(row).model_dump(),
        scored=row["scored"] or 0,
        spend=Spend(
            calls=row["calls"] or 0,
            replayed=row["replayed"] or 0,
            tokens_in=row["tokens_in"] or 0,
            tokens_out=row["tokens_out"] or 0,
            usd=None if row["usd"] is None else float(row["usd"]),
        ),
        duration_ms=_elapsed(row["first_wrote"], row["last_wrote"]),
        manifest=row["manifest"],
        directions=directions,
        baseline=row["baseline"],
        cap_trials=cap_trials,
    )


#: The candidate this trial produced, and the one it was made from. Both
#: reached through blobs, which is where the source actually lives -- the
#: trial row holds fingerprints and nothing else.
MINE = candidates.alias("mine")
THEIRS = candidates.alias("theirs")
CODE = blobs.alias("code")
PARENT_CODE = blobs.alias("parent_code")

DETAILED = (
    trials.outerjoin(
        MINE,
        sa.and_(
            MINE.c.run_id == trials.c.run_id,
            MINE.c.fingerprint == trials.c.candidate_fingerprint,
        ),
    )
    .outerjoin(verdicts, verdicts.c.candidate_hash == MINE.c.fingerprint)
    .outerjoin(CODE, CODE.c.hash == MINE.c.code_hash)
    .outerjoin(
        THEIRS,
        sa.and_(
            THEIRS.c.run_id == trials.c.run_id,
            THEIRS.c.fingerprint == trials.c.parent_fingerprint,
        ),
    )
    .outerjoin(PARENT_CODE, PARENT_CODE.c.hash == THEIRS.c.code_hash)
    # The calls that came back. A trial that was retried has more than one,
    # and the last of them can be one that was written before the call and
    # never answered -- a run killed mid-request leaves exactly that. Joining
    # to it would report a trial as having no model, no tokens and nothing
    # said, when the answer it used is sitting in the row before.
    #
    # In the ON clause rather than a WHERE, or the outer join stops being one
    # and a trial that never got as far as asking vanishes from its own page.
    .outerjoin(
        model_calls,
        sa.and_(
            model_calls.c.trial_id == trials.c.id,
            model_calls.c.status == "done",
        ),
    )
)

DETAIL_COLUMNS = (
    trials,
    verdicts.c.outcome,
    verdicts.c.metrics,
    verdicts.c.wall_ms,
    CODE.c.body.label("code"),
    PARENT_CODE.c.body.label("parent_code"),
    model_calls.c.model,
    model_calls.c.tokens_in,
    model_calls.c.tokens_out,
    model_calls.c.latency_ms,
    model_calls.c.cost_usd,
    model_calls.c.response,
)


def trial_detail(session: Session, trial_id: str) -> TrialDetail | None:
    """One trial, with what it cost and what it changed.

    The diff is computed here rather than stored. Both programs are already
    in blobs, keyed by content, so a diff made on the way out is one that
    cannot disagree with the two blobs it came from -- and there is no column
    to migrate and nobody to keep it up to date.
    """
    row = (
        session.execute(
            sa.select(*DETAIL_COLUMNS)
            .select_from(DETAILED)
            .where(trials.c.id == trial_id)
            # The most recent answered call: the one whose reply became the
            # candidate on this page.
            .order_by(model_calls.c.occurred_at.desc())
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return TrialDetail(
        **_trial(row).model_dump(),
        wall_ms=row["wall_ms"],
        model=row["model"],
        tokens_in=row["tokens_in"],
        tokens_out=row["tokens_out"],
        latency_ms=row["latency_ms"],
        cost_usd=None if row["cost_usd"] is None else float(row["cost_usd"]),
        code=row["code"],
        diff=_diff(row["parent_code"], row["code"]),
        response=row["response"],
    )


def some_experiments(session: Session, limit: int = PAGE) -> list[ExperimentSummary]:
    """Runs grouped by the name they were started under.

    Derived, because there is no experiments table to read: `experiment` is a
    column each run copies off its manifest. Runs that named nothing are left
    out rather than collected under a blank -- "" is not an experiment, it is
    the absence of one, and a row for it would sort into the middle of a list
    of real ones.
    """
    rows = session.execute(
        sa.select(
            runs.c.experiment,
            sa.func.count().label("runs"),
            sa.func.count(sa.case((runs.c.status == RunState.RUNNING, 1))).label(
                "running"
            ),
            sa.func.max(runs.c.started_at).label("last_activity"),
            # The best of the most recent run that has one. Most recent
            # rather than highest scoring: which of two metrics is better is
            # the manifest's business, and a rollup that has not read a
            # manifest is not entitled to an opinion about it.
            #
            # In the GROUP BY rather than a lookup per row -- this list is
            # refetched every few seconds while anything is running, and a
            # query per experiment is a query per experiment per poll.
            sa.func.array_agg(aggregate_order_by(runs.c.best, runs.c.started_at.desc()))
            .filter(runs.c.best.isnot(None))[1]
            .label("best"),
        )
        .where(runs.c.experiment.isnot(None))
        .group_by(runs.c.experiment)
        .order_by(sa.func.max(runs.c.started_at).desc())
        .limit(limit)
    ).mappings()
    return [
        ExperimentSummary(
            name=row["experiment"],
            runs=row["runs"],
            running=row["running"],
            best=row["best"],
            last_activity=row["last_activity"],
        )
        for row in rows
    ]


def _elapsed(first: datetime | None, last: datetime | None) -> float | None:
    if first is None or last is None:
        return None
    return (last - first).total_seconds() * 1000


def _diff(parent: str | None, code: str | None) -> str | None:
    """What changed, or None when there is nothing to compare.

    None and "" are different answers and the page says so differently: a
    trial whose patch was rejected produced no candidate at all, and a trial
    that produced one identical to its parent changed nothing. Only the
    second of those is an empty diff.
    """
    if code is None:
        return None
    return "".join(
        difflib.unified_diff(
            (parent or "").splitlines(keepends=True),
            code.splitlines(keepends=True),
            fromfile="parent",
            tofile="candidate",
        )
    )
