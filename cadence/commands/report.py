"""How a command talks.

Findings go to stdout in two columns: what was checked, and what was found.
Anything that is not a finding goes to stderr, so `cadence check > findings`
keeps only the findings.
"""

import typer

LABEL = 12


def found(label: str, detail: str) -> None:
    """A check that passed, and what it saw."""
    typer.echo(f"  {label:<{LABEL}}{detail}")


def absent(label: str, detail: str) -> None:
    """Something optional that is not there. Not a failure."""
    typer.echo(f"  {label:<{LABEL}}{detail}")


def note(line: str) -> None:
    typer.echo(line, err=True)


def die(message: str, fix: str | None = None) -> None:
    typer.echo(f"\n{message}", err=True)
    if fix:
        typer.echo(f"\n{fix}", err=True)
    raise typer.Exit(1)
