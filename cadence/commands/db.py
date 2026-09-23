"""The database cadence records into: what state it is in, and moving it.

Every verb takes --url, because migrating and running are different jobs:
migrating needs the role that owns the schema, running needs the one that
writes rows. Making people swap DATABASE_URL between the two is how the wrong
one ends up exported.

Nothing here runs by itself. A run that meets an out-of-date schema still
refuses and names the command, rather than migrating somebody's database
because they happened to start a run.
"""

import os

import typer

from cadence.commands.report import absent, die, found, json_capable, note
from cadence.control import schema
from cadence.control.storage import APP_ROLE
from cadence.core.dto import SchemaState
from cadence.errors import CadenceError

app = typer.Typer(no_args_is_help=True, help="The database runs are recorded in.")

URL = typer.Option(None, "--url", help="Which database. Default: DATABASE_URL.")
JSON = typer.Option(False, "--json/--no-json", help="Output as JSON.")


def _url(given: str | None) -> str:
    url = given or os.environ.get("DATABASE_URL")
    if not url:
        die(
            "no database to work on: DATABASE_URL is not set.",
            "Set it, or pass --url postgresql://...",
        )
    return url


def _state(url: str) -> SchemaState:
    try:
        return schema.state(url)
    except CadenceError as error:
        die(str(error))


@app.command()
@json_capable
def status(url: str | None = URL, json_output: bool = JSON) -> None:
    """What this database is, and what a run would make of it."""
    state = _state(_url(url))
    found("database", state.where)
    found("schema", state.at or "no cadence schema in it yet")
    found("cadence", f"writes {state.expected}")
    if state.app_role:
        found("app role", f"{APP_ROLE} exists, so a run may connect as it")
    else:
        absent("app role", f"no {APP_ROLE}: a run connects as the owner")

    if state.is_current:
        note("\nready. `cadence run` will record into this database.")
        return
    pending = len(state.pending)
    absent(
        "to apply",
        f"{pending} migration{'' if pending == 1 else 's'}"
        if pending
        else f"none: this cadence does not write {state.at}",
    )
    note("\n`cadence db upgrade` brings it up to date.")
    raise typer.Exit(1)


@app.command()
@json_capable
def upgrade(
    url: str | None = URL,
    to: str = typer.Option("head", "--to", metavar="REVISION"),
    json_output: bool = JSON,
) -> None:
    """Apply the migrations this cadence needs."""
    where = _url(url)
    state = _state(where)
    if state.is_current and to == "head":
        found("database", f"{state.where} is already at {state.expected}")
        return
    found("database", state.where)
    found("applying", f"{len(state.pending)} to reach {to}")
    try:
        schema.upgrade(where, to)
    except CadenceError as error:
        die(str(error))
    found("now at", _state(where).at or "nothing")


@app.command()
@json_capable
def rollback(
    url: str | None = URL,
    to: str = typer.Option("-1", "--to", metavar="REVISION", help="Or -1, -2, ..."),
    yes: bool = typer.Option(False, "--yes", help="Do not ask."),
    json_output: bool = JSON,
) -> None:
    """Undo migrations. It can drop tables, so it asks first."""
    where = _url(url)
    state = _state(where)
    found("database", state.where)
    found("schema", state.at or "no cadence schema in it yet")
    found("rolling to", to)
    if not yes:
        typer.confirm("This can delete recorded runs. Continue?", abort=True)
    try:
        schema.downgrade(where, to)
    except CadenceError as error:
        die(str(error))
    found("now at", _state(where).at or "no cadence schema left")
