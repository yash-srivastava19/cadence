"""Run commands."""

import typer

from cadence.cli.config import get_session
from cadence.cli.format import CLIFormatter
from cadence.cli.queries import RunQueries

app = typer.Typer(help="Manage runs")


@app.command()
def list(
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(100, "--limit", help="Max results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all runs.

    Examples:
        cadence run list
        cadence run list --status=RUNNING
        cadence run list --json
    """
    try:
        session = get_session()
        data = RunQueries.list(session, status=status, limit=limit)

        if json_output:
            output = CLIFormatter.json(data)
        else:
            columns = ["id", "status", "trials", "best_score", "started_at"]
            output = CLIFormatter.table(data, columns)

        typer.echo(output)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def describe(run_id: str):
    """Describe a run.

    Examples:
        cadence run describe run-123
    """
    try:
        session = get_session()
        data = RunQueries.get(session, run_id)

        if not data:
            typer.echo(f"Run {run_id} not found", err=True)
            raise typer.Exit(1) from None

        output = CLIFormatter.one(data)
        typer.echo(output)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None
