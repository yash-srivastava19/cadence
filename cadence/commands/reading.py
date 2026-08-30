"""What the query commands share: a session, and how to print an answer."""

import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import typer
from sqlalchemy.orm import Session

from cadence.commands.report import die
from cadence.control.storage import sessions, translating
from cadence.core.values import Value
from cadence.delivery import as_json

__all__ = ["reading", "show", "wanted_json"]


@contextmanager
def reading() -> Iterator[Session]:
    """A session for looking, with the same door checks a run gets.

    sessions() refuses a database whose schema is not the one this code
    writes, and translating() turns a driver error into the one sentence
    about the database rather than a psycopg traceback.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        die(
            "there is nothing to read: DATABASE_URL is not set.",
            "Runs are only recorded when DATABASE_URL points at a database.",
        )
    with translating(), sessions(url)() as session:
        yield session


def wanted_json(asked: bool | None) -> bool:
    """--json and --no-json settle it. Otherwise, whoever is reading does.

    A pipe, a log and a CI job all want JSON and none of them can say so, so
    not being a terminal is taken as asking for it.
    """
    if asked is not None:
        return asked
    return not sys.stdout.isatty()


def show(value: Value | Sequence[Value], as_text: str, asked: bool | None) -> None:
    typer.echo(as_json(value) if wanted_json(asked) else as_text)
