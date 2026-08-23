import os

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, registry, sessionmaker

from cadence.entities import Run
from cadence.states import RunState

__all__ = ["metadata", "runs", "engine", "sessions", "dsn"]

DRIVER = "postgresql+psycopg://"

mapper_registry = registry()
metadata = mapper_registry.metadata


def stored(enum, name):
    return sa.Enum(enum, name=name, values_callable=lambda e: [m.value for m in e])


runs = sa.Table(
    "runs",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("status", stored(RunState, "run_state"), nullable=False),
    sa.Column("trials", sa.Integer, nullable=False, server_default="0"),
    sa.Column("best", sa.Text),
    sa.Column("reason", sa.Text),
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
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
