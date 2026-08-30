"""Looking at runs that have already happened.

Plural, because `cadence run` is the verb that starts one. Two words that
differ by an "s" is not much of a distinction, but the alternative is one
word meaning both "do this" and "tell me about that".
"""

import typer

from cadence.commands.identity import owner as whoami
from cadence.commands.reading import reading, show
from cadence.commands.report import die
from cadence.control.queries import PAGE, one_run, some_runs
from cadence.delivery import one_as_text, runs_as_text

app = typer.Typer(no_args_is_help=True, help="Runs that were recorded.")


@app.command("list")
def list_(
    experiment: str | None = typer.Option(None, "--experiment", "-e"),
    owner: str | None = typer.Option(None, "--owner"),
    mine: bool = typer.Option(False, "--mine", help="Only runs you started."),
    status: str | None = typer.Option(None, "--status"),
    limit: int = typer.Option(PAGE, "--limit"),
    json_: bool | None = typer.Option(None, "--json/--no-json"),
) -> None:
    """List recorded runs, newest first."""
    if mine and owner:
        die("--mine and --owner ask for different people; pick one.")
    if mine:
        owner = whoami()
        if owner is None:
            die(
                "--mine needs to know who you are.",
                "Set CADENCE_OWNER, or git config user.email.",
            )
    with reading() as session:
        found = some_runs(session, experiment, owner, status, limit)
    show(found, runs_as_text(found), json_)


@app.command("show")
def show_(
    run_id: str = typer.Argument(..., metavar="RUN_ID"),
    json_: bool | None = typer.Option(None, "--json/--no-json"),
) -> None:
    """Everything recorded about one run."""
    with reading() as session:
        found = one_run(session, run_id)
    if found is None:
        die(f"no run called {run_id!r}.", "cadence runs list shows what there is.")
    show(found, one_as_text(found), json_)
