"""Trial commands."""

import typer

from cadence.cli.config import get_session
from cadence.cli.format import CLIFormatter
from cadence.cli.queries import TrialQueries

app = typer.Typer(help="Manage trials")


@app.command()
def list(
    run_id: str = typer.Option(..., "--run", help="Run ID (required)"),
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(100, "--limit", help="Max results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List trials in a run.

    Examples:
        cadence trial list --run=run-123
        cadence trial list --run=run-123 --status=TIMEOUT
        cadence trial list --run=run-123 --json
    """
    try:
        session = get_session()
        data = TrialQueries.list(session, run_id, status=status, limit=limit)

        if json_output:
            output = CLIFormatter.json(data)
        else:
            columns = ["id", "seq", "status", "started_at"]
            output = CLIFormatter.table(data, columns)

        typer.echo(output)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def describe(trial_id: str):
    """Describe a trial.

    Examples:
        cadence trial describe trial-999
    """
    try:
        session = get_session()
        data = TrialQueries.get(session, trial_id)

        if not data:
            typer.echo(f"Trial {trial_id} not found", err=True)
            raise typer.Exit(1) from None

        output = CLIFormatter.one(data)
        typer.echo(output)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None
