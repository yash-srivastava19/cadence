"""Cadence CLI entry point."""

import typer

from cadence.cli.commands import run, trial

app = typer.Typer()
app.add_typer(run.app, name="run")
app.add_typer(trial.app, name="trial")

if __name__ == "__main__":
    app()
