import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import typer

from cadence.commands.report import die, note
from cadence.control.manifest import load
from cadence.control.registry import build
from cadence.errors import CadenceError
from cadence.observe.signals import cadence


@contextmanager
def _remembering() -> Iterator[Any]:
    """Give the run a memory, if there is somewhere to keep one.

    DATABASE_URL is what decides. Without it the loop runs exactly as before
    and keeps everything in its head -- which is what lets the example run
    with no database, no key and no network.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        yield None
        return
    from cadence.control.journal import Journal
    from cadence.control.storage import sessions

    with sessions(url)() as session:
        stop = cadence.record(Journal(session).record)
        try:
            yield session
        finally:
            stop()


def _what_it_spent(spend) -> str:
    """Tokens, and how many of them were not bought again.

    A run that reports what it found and not what it cost cannot be compared
    with another one -- best-found is incomparable across runs that spent
    differently, which is every comparison a person actually makes.
    """
    replayed = f", {spend.replayed} replayed" if spend.replayed else ""
    return (
        f"{spend.calls} model call{'s' if spend.calls != 1 else ''}{replayed},"
        f" {spend.tokens:,} tokens"
        f" ({spend.tokens_in:,} in, {spend.tokens_out:,} out)"
    )


def _what_it_remembers(experiment, run_id: str) -> str:
    resumed = experiment.resumed
    if resumed is None:
        return f"recording run {run_id}"
    return (
        f"resuming run {run_id} from trial {resumed.trials}"
        f" with {len(resumed.history.results)} results already scored"
    )


def run(
    root: Path = typer.Argument(Path(".")),
    run_id: str = typer.Option("local", "--id"),
) -> None:
    """Improve the program named by .cadence."""
    try:
        with _remembering() as session:
            experiment = build(load(root), root, run_id, session=session)
            if session is not None:
                note(_what_it_remembers(experiment, run_id))
            report = experiment.run()
    except CadenceError as error:
        die(str(error))
        raise  # unreachable; die() exits. keeps `report` definitely bound.
    typer.echo(f"\n{report.status}  {report.scored}/{report.trials} scored")
    typer.echo(_what_it_spent(report.spend))
    if report.reason:
        die(report.reason)
    if report.metrics:
        for name, value in report.metrics.items():
            typer.echo(f"  {name} = {value:g}")
        typer.echo(f"\n{report.program}")
