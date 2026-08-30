"""Looking at the trials inside a run."""

import typer

from cadence.commands.reading import reading, show
from cadence.commands.report import die
from cadence.control.queries import PAGE, one_trial, some_trials
from cadence.delivery import one_as_text, trials_as_text

app = typer.Typer(no_args_is_help=True, help="Trials inside a run.")


@app.command("list")
def list_(
    run_id: str = typer.Option(..., "--run", help="Which run's trials."),
    status: str | None = typer.Option(None, "--status"),
    limit: int = typer.Option(PAGE, "--limit"),
    json_: bool | None = typer.Option(None, "--json/--no-json"),
) -> None:
    """List the trials of one run, in the order they were tried."""
    with reading() as session:
        found = some_trials(session, run_id, status, limit)
    show(found, trials_as_text(found), json_)


@app.command("show")
def show_(
    trial_id: str = typer.Argument(..., metavar="TRIAL_ID"),
    json_: bool | None = typer.Option(None, "--json/--no-json"),
) -> None:
    """Everything recorded about one trial."""
    with reading() as session:
        found = one_trial(session, trial_id)
    if found is None:
        die(f"no trial called {trial_id!r}.")
    show(found, one_as_text(found), json_)
