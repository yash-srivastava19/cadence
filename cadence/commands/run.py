import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import typer

from cadence.commands.report import die, note
from cadence.control.manifest import load
from cadence.control.preflight import inspect
from cadence.control.registry import build, seed_program
from cadence.delivery import as_json, as_text
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


def _refuse_a_project_check_would_refuse(manifest, root: Path) -> None:
    """The same checks, from both doors.

    Without this, `cadence check` refuses an unmarked program and `cadence
    run` accepts it and rewrites the whole file on every trial -- two entry
    points with two definitions of a valid project, and the expensive one is
    the lenient one.

    Only the free half. Rehearsing the scoring command is check's job: run
    would be spending a subprocess to re-learn what check already said, and
    for a verifier that takes forty seconds that is a real bill.
    """
    preflight = inspect(manifest, root, seed_program(manifest, root))
    for finding in preflight.wrong:
        die(finding.detail, finding.fix)


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
    as_json_output: bool = typer.Option(
        False, "--json", help="Print the report as JSON instead of text."
    ),
) -> None:
    """Improve the program named by .cadence."""
    try:
        manifest = load(root)
        _refuse_a_project_check_would_refuse(manifest, root)
        with _remembering() as session:
            experiment = build(manifest, root, run_id, session=session)
            if session is not None:
                note(_what_it_remembers(experiment, run_id))
            report = experiment.run()
    except CadenceError as error:
        die(str(error))
        raise  # unreachable; die() exits. keeps `report` definitely bound.
    typer.echo(as_json(report) if as_json_output else f"\n{as_text(report)}")
    if report.reason:
        raise typer.Exit(1)
