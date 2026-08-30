import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import typer

from cadence.commands.identity import fresh_id, owner
from cadence.commands.reading import wanted_json
from cadence.commands.report import die, note
from cadence.control.manifest import load
from cadence.control.preflight import inspect
from cadence.control.registry import build, seed_program
from cadence.control.restore import status_of
from cadence.delivery import as_json, as_text
from cadence.errors import CadenceError
from cadence.lifecycle.states import RunState
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


def _refuse_to_overwrite(session, run_id: str, resume: str | None) -> None:
    """A run id is claimed once.

    Without this, starting a run under an id the database already has fails
    on the primary key somewhere inside the journal. Worse before ids were
    generated: everyone's run was called "local", so the second person to
    share a database silently continued the first one's experiment.
    """
    known = status_of(session, run_id)
    if resume and known is None:
        die(f"no run called {run_id!r} to resume.")
    if not resume and known is not None:
        die(
            f"run {run_id!r} is already recorded ({known}).",
            f"Use 'cadence run --resume {run_id}' to carry it on,"
            " or leave --id off to start a new one.",
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
    run_id: str | None = typer.Option(
        None, "--id", help="Name this run. One is generated if you do not."
    ),
    resume: str | None = typer.Option(
        None, "--resume", metavar="RUN_ID", help="Carry on a run that stopped."
    ),
    as_json_output: bool | None = typer.Option(
        None, "--json/--no-json", help="JSON instead of text. Default off a terminal."
    ),
) -> None:
    """Improve the program named by .cadence."""
    if resume and run_id:
        die("--resume names the run to carry on; --id would name a different one.")
    run_id = resume or run_id or fresh_id()
    try:
        manifest = load(root)
        _refuse_a_project_check_would_refuse(manifest, root)
        with _remembering() as session:
            if session is not None:
                _refuse_to_overwrite(session, run_id, resume)
            experiment = build(
                manifest,
                root,
                run_id,
                session=session,
                owner=owner(),
                resume=resume is not None,
            )
            if session is not None:
                note(_what_it_remembers(experiment, run_id))
            report = experiment.run()
    except CadenceError as error:
        die(str(error))
        raise  # unreachable; die() exits. keeps `report` definitely bound.
    if wanted_json(as_json_output):
        typer.echo(as_json(report))
    else:
        typer.echo(f"\n{as_text(report)}")
    # The status, not the message: a run that stopped at its cap did what it
    # was told and has a sentence about it.
    if report.status is not RunState.FINISHED:
        raise typer.Exit(1)
