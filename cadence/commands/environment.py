"""Reading .env, because docker compose does and cadence did not.

The gap this closes: DATABASE_URL sits in .env, `docker compose up` reads it,
and `cadence runs list` says "DATABASE_URL is not set". To get anywhere you
had to know the file exists, know cadence ignored it, and run
`set -a; source .env; set +a`.

Precedence, highest first:

    the real environment      exported wins, always
    .env in the directory     the same file compose reads

A real shell is not being emulated. No interpolation, no multi-line values,
no `$VAR` expansion: a line is NAME=VALUE, optionally quoted, optionally
prefixed with `export`. Anything else is skipped rather than guessed at,
because a DSN read wrong is worse than a DSN not read.

# ponytail: cwd only, no walking up to a project root. Add that when someone
# runs cadence from a subdirectory and it surprises them.
"""

import os
from pathlib import Path

__all__ = ["FILENAME", "load_env", "read_env"]

FILENAME = ".env"


def read_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip().removeprefix("export ").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if not name.isidentifier():
            continue
        value = value.strip()
        # Quotes come off whole or not at all. A value that opens a quote and
        # does not close it is a line this parser does not understand.
        for quote in ('"', "'"):
            if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
                value = value[1:-1]
                break
        else:
            # Unquoted values end at a comment, the way compose reads them.
            value = value.split(" #")[0].rstrip()
        values[name] = value
    return values


def load_env(directory: Path | None = None) -> None:
    """Put .env into the environment, without overwriting what is there."""
    path = (directory or Path.cwd()) / FILENAME
    try:
        text = path.read_text()
    except OSError:  # missing, unreadable, a directory -- all mean "no .env"
        return
    for name, value in read_env(text).items():
        os.environ.setdefault(name, value)
