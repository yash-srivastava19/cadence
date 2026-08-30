import os
from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, registry, sessionmaker

from cadence.control.entities import Run
from cadence.core.verdict import Outcome
from cadence.errors import SchemaOutOfDate, StorageError
from cadence.lifecycle.states import CandidateState, RunState, TrialState

__all__ = [
    "EXPECTED_REVISION",
    "blobs",
    "budget",
    "candidates",
    "demand_current_schema",
    "dsn",
    "engine",
    "events",
    "manifests",
    "metadata",
    "model_calls",
    "revision_of",
    "runs",
    "sessions",
    "templates",
    "translating",
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
    # Copied from the manifest rather than joined for: manifests are keyed by
    # content, so bumping the budget makes a new one and would split a group.
    sa.Column("experiment", sa.Text),
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

mapper_registry.map_imperatively(Run, runs)


@event.listens_for(Run, "load")
def _rebind(target, context):
    target.bind()


def dsn(url: str | None = None) -> str:
    url = url or os.environ["DATABASE_URL"]
    return url.replace("postgresql://", DRIVER, 1)


def engine(url: str | None = None, **kwargs) -> Engine:
    return sa.create_engine(dsn(url), **kwargs)


#: The migration this code writes against. A test reads alembic's head and
#: asserts they match, so adding a migration without updating this constant
#: fails in CI rather than at somebody's first run.
EXPECTED_REVISION = "c4e81b90d7a2"


def revision_of(connection: Connection) -> str | None:
    """Which migration the database has been brought up to, if any.

    None covers both "empty database" and "someone else's database": neither
    has an alembic_version table, and neither is somewhere cadence should
    start writing rows.
    """
    if not sa.inspect(connection).has_table("alembic_version"):
        return None
    return connection.execute(
        sa.text("select version_num from alembic_version")
    ).scalar()


def demand_current_schema(bound: Engine) -> None:
    """Refuse a database whose schema is not the one this code writes.

    Checked once, at the door, because the alternative is what it replaces: a
    psycopg traceback from the middle of the first trial, naming whichever
    table happened to be written to first, which tells the user nothing about
    what to do next.
    """
    with connecting(bound) as connection:
        found = revision_of(connection)
    if found == EXPECTED_REVISION:
        return
    if found is None:
        raise SchemaOutOfDate(
            "the database has no cadence schema in it."
            " Run 'alembic upgrade head' against DATABASE_URL,"
            " or unset DATABASE_URL to run without recording anything"
        )
    raise SchemaOutOfDate(
        f"the database is at migration {found} and this cadence writes"
        f" {EXPECTED_REVISION}. Run 'alembic upgrade head' against DATABASE_URL"
    )


@contextmanager
def translating() -> Iterator[None]:
    """Every way the database can fail, turned into a value in one place.

    Rule 5: a failure crosses a plane boundary as a value, not as whatever the
    driver happened to raise. Below this line psycopg exists; above it only
    StorageError does, and the command has one thing to catch.

    A context manager rather than a decorator because the two callers wrap
    different things -- a connection here, a whole unit of work in the journal
    -- and both need whatever they were holding released on the way out.
    """
    try:
        yield
    except SQLAlchemyError as error:
        raise StorageError(_said(error)) from error


@contextmanager
def connecting(bound: Engine) -> Iterator[Connection]:
    with translating(), bound.connect() as connection:
        yield connection


def _said(error: SQLAlchemyError) -> str:
    """The driver's own words, without the SQL that produced them.

    A psycopg error stringifies to the statement and its parameters as well,
    which is a wall of text about our query when the user needs the sentence
    about their database.
    """
    original = getattr(error, "orig", None)
    return str(original or error).strip().splitlines()[0]


def sessions(url: str | None = None, **kwargs) -> sessionmaker[Session]:
    """A session factory, once the database has been shown to be usable.

    The check belongs here rather than in the command because this is the one
    door: every entry point that records anything comes through it, which is
    the same reason preflight lives in one place.
    """
    bound = engine(url, **kwargs)
    demand_current_schema(bound)
    return sessionmaker(bind=bound, expire_on_commit=False)
