import os

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry, sessionmaker

from cadence.control.entities import Run
from cadence.core.verdict import Outcome
from cadence.lifecycle.states import CandidateState, RunState, TrialState

__all__ = [
    "blobs",
    "budget",
    "candidates",
    "dsn",
    "engine",
    "events",
    "idempotency_keys",
    "manifests",
    "metadata",
    "model_calls",
    "quarantine",
    "runs",
    "sessions",
    "templates",
    "trials",
    "verdicts",
]

DRIVER = "postgresql+psycopg://"

mapper_registry = registry()
metadata = mapper_registry.metadata


def stored(enum, name):
    return sa.Enum(enum, name=name, values_callable=lambda e: [m.value for m in e])


def _hash(name, *args, **kwargs):
    """A content address: sha256 hex, so a fixed width."""
    return sa.Column(name, sa.String(HASH_WIDTH), *args, **kwargs)


def _when(name, **kwargs):
    return sa.Column(name, sa.DateTime(timezone=True), **kwargs)


HASH_WIDTH = 64


# --- content-addressed: the hash is the body, so a row can never change ----

blobs = sa.Table(
    "blobs",
    metadata,
    _hash("hash", primary_key=True),
    sa.Column("body", sa.Text, nullable=False),
    _when("first_seen", nullable=False, server_default=sa.func.now()),
    comment="Candidate source, stored once however many candidates share it.",
)

manifests = sa.Table(
    "manifests",
    metadata,
    _hash("hash", primary_key=True),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("api_version", sa.Text, nullable=False),
    _when("first_seen", nullable=False, server_default=sa.func.now()),
    comment="The .cadence that produced a run, verbatim.",
)

templates = sa.Table(
    "templates",
    metadata,
    _hash("hash", primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("body", sa.Text, nullable=False),
    _when("first_seen", nullable=False, server_default=sa.func.now()),
    comment=(
        "Prompt templates by content. Editing one in code adds a row rather"
        " than changing one, so a past prompt stays reproducible."
    ),
)


# --- the run, and what it did --------------------------------------------

runs = sa.Table(
    "runs",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("status", stored(RunState, "run_state"), nullable=False),
    sa.Column("trials", sa.Integer, nullable=False, server_default="0"),
    sa.Column("best", sa.Text),
    sa.Column("reason", sa.Text),
    _when("started_at", nullable=False, server_default=sa.func.now()),
    # Nullable until the loop opens a session and starts recording these.
    _hash("manifest_hash", nullable=True),
    sa.Column("owner", sa.Text),
    _when("lease_expires_at"),
    sa.ForeignKeyConstraint(["manifest_hash"], ["manifests.hash"]),
)

trials = sa.Table(
    "trials",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("run_id", sa.Text, sa.ForeignKey("runs.id"), nullable=False),
    sa.Column("seq", sa.Integer, nullable=False),
    sa.Column("status", stored(TrialState, "trial_state"), nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    _hash("parent_fingerprint"),
    # What it produced. Null until the patch applies, and for good if it never
    # does: an abandoned trial made nothing.
    _hash("candidate_fingerprint"),
    sa.Column("reason", sa.Text),
    sa.Column("owner", sa.Text),
    _when("lease_expires_at"),
    sa.Column("idempotency_key", sa.Text),
    _when("started_at", nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("run_id", "seq"),
)

candidates = sa.Table(
    "candidates",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("run_id", sa.Text, sa.ForeignKey("runs.id"), nullable=False),
    _hash("fingerprint", nullable=False),
    _hash("code_hash", sa.ForeignKey("blobs.hash"), nullable=False),
    sa.Column("parent_id", sa.Text, sa.ForeignKey("candidates.id")),
    sa.Column("status", stored(CandidateState, "candidate_state"), nullable=False),
    sa.Column("crashes", sa.Integer, nullable=False, server_default="0"),
    _when("created_at", nullable=False, server_default=sa.func.now()),
    # The dedup a plain hash column never gave us.
    sa.UniqueConstraint("run_id", "fingerprint"),
)

verdicts = sa.Table(
    "verdicts",
    metadata,
    _hash("candidate_hash", primary_key=True),
    _hash("task_hash", primary_key=True),
    _hash("seeds_hash", primary_key=True),
    sa.Column("outcome", stored(Outcome, "outcome"), nullable=False),
    sa.Column("metrics", postgresql.JSONB),
    sa.Column("reason", sa.Text),
    sa.Column("wall_ms", sa.Float),
    # Two clocks: a trial that starts first can finish second, so ordering by
    # the time we wrote it down would quietly rewrite what happened.
    _when("occurred_at", nullable=False),
    _when("recorded_at", nullable=False, server_default=sa.func.now()),
    comment=(
        "The primary key is the cache. Sound only if the verifier is deterministic."
    ),
)

events = sa.Table(
    "events",
    metadata,
    sa.Column("run_id", sa.Text, sa.ForeignKey("runs.id"), primary_key=True),
    sa.Column("seq", sa.Integer, primary_key=True),
    sa.Column("type", sa.Text, nullable=False),
    sa.Column("payload", postgresql.JSONB, nullable=False),
    _when("occurred_at", nullable=False),
    _when("recorded_at", nullable=False, server_default=sa.func.now()),
    comment="The tape. Append-only; an event that could change is not an event.",
)


# --- what it cost, and what must not be run again -------------------------

model_calls = sa.Table(
    "model_calls",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("run_id", sa.Text, sa.ForeignKey("runs.id"), nullable=False),
    sa.Column("trial_id", sa.Text, sa.ForeignKey("trials.id")),
    _hash("request_hash", nullable=False),
    _hash("template_hash", sa.ForeignKey("templates.hash")),
    sa.Column("recipe", postgresql.JSONB, nullable=False),
    sa.Column("response", sa.Text),
    sa.Column("model", sa.Text),
    sa.Column("latency_ms", sa.Float),
    sa.Column("tokens_in", sa.Integer),
    sa.Column("tokens_out", sa.Integer),
    sa.Column("cost_usd", sa.Numeric(12, 6)),
    sa.Column("status", sa.Text, nullable=False),
    _when("occurred_at", nullable=False),
    _when("recorded_at", nullable=False, server_default=sa.func.now()),
    comment="The recipe must rebuild the prompt byte for byte, or replay is unsound.",
)

budget = sa.Table(
    "budget",
    metadata,
    sa.Column("run_id", sa.Text, sa.ForeignKey("runs.id"), primary_key=True),
    sa.Column("cap_trials", sa.Integer),
    sa.Column("cap_usd", sa.Numeric(12, 6)),
    sa.Column("reserved_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    sa.Column("settled_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    comment="Reserve before dispatch, settle after. Check-then-spend is two steps.",
)

quarantine = sa.Table(
    "quarantine",
    metadata,
    _hash("fingerprint", primary_key=True),
    sa.Column("run_id", sa.Text, sa.ForeignKey("runs.id"), nullable=False),
    sa.Column("reason", sa.Text, nullable=False),
    sa.Column("crashes", sa.Integer, nullable=False),
    _when("at", nullable=False, server_default=sa.func.now()),
    comment="Read at dispatch. A poison candidate surviving restart loops forever.",
)

idempotency_keys = sa.Table(
    "idempotency_keys",
    metadata,
    sa.Column("key", sa.Text, primary_key=True),
    sa.Column("scope", sa.Text, nullable=False),
    _hash("request_hash", nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("response_body", sa.Text),
    sa.Column("response_code", sa.Integer),
    _when("locked_at"),
    _when("expires_at", nullable=False),
    sa.CheckConstraint("status in ('in_flight', 'done')", name="idempotency_status"),
    comment="The one table a sweeper deletes from, hence the DELETE grant.",
)

mapper_registry.map_imperatively(Run, runs)


@event.listens_for(Run, "load")
def _rebind(target, context):
    target.bind()


def dsn(url: str | None = None) -> str:
    url = url or os.environ["DATABASE_URL"]
    return url.replace("postgresql://", DRIVER, 1)


def engine(url: str | None = None, **kwargs) -> Engine:
    return sa.create_engine(dsn(url), **kwargs)


def sessions(url: str | None = None, **kwargs) -> sessionmaker[Session]:
    return sessionmaker(bind=engine(url, **kwargs), expire_on_commit=False)
