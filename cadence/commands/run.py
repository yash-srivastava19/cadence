import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from cadence.commands.report import die, note
from cadence.control.manifest import load
from cadence.control.registry import build
from cadence.errors import CadenceError
from cadence.observe.signals import cadence


@contextmanager
def _writing_it_down() -> Iterator[bool]:
    """Record the run, if there is somewhere to record it.

    DATABASE_URL is what decides. Without it the loop runs exactly as before
    and keeps everything in memory -- which is what lets the example run with
    no database, no key and no network.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        yield False
        return
    from cadence.control.journal import Journal
    from cadence.control.storage import sessions

    with sessions(url)() as session:
        stop = cadence.record(Journal(session).record)
        try:
            yield True
        finally:
            stop()


def run(
    root: Path = typer.Argument(Path(".")),
    run_id: str = typer.Option("local", "--id"),
) -> None:
    """Improve the program named by .cadence."""
    try:
        experiment = build(load(root), root, run_id)
        with _writing_it_down() as recorded:
            if recorded:
                note(f"recording run {run_id}")
            report = experiment.run()
    except CadenceError as error:
        die(str(error))
        raise  # unreachable; die() exits. keeps `report` definitely bound.
    typer.echo(f"\n{report.status}  {report.scored}/{report.trials} scored")
    if report.reason:
        die(report.reason)
    if report.metrics:
        for name, value in report.metrics.items():
            typer.echo(f"  {name} = {value:g}")
        typer.echo(f"\n{report.program}")
