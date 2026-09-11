"""Serving what was recorded, to a browser.

The listing commands with a different way in: same session, same queries,
same JSON. Read-only, and bound to localhost -- there is no authentication
here and everything a run recorded, manifest and source included, is readable
through it.
"""

import typer

from cadence.commands.reading import reading
from cadence.commands.report import found, note
from cadence.web import serve


def dashboard(
    port: int = typer.Option(8787, "--port", "-p"),
    host: str = typer.Option("127.0.0.1", "--host", help="Localhost by default."),
) -> None:
    """Browse experiments, runs and trials in a browser."""
    # `reading` dies with a sentence when DATABASE_URL is missing or the
    # schema is stale. Calling it once here means the user finds out now,
    # rather than in a browser tab after the first fetch.
    with reading():
        pass
    found("serving", f"http://{host}:{port}")
    note("ctrl-c to stop")
    try:
        serve(reading, port, host)
    except KeyboardInterrupt:
        note("stopped")
