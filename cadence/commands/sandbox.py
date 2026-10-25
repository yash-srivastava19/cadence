"""The far end of a remote sandbox: measure one job, on this machine."""

import sys

import typer

from cadence.execution.sandboxes.remote import answer


def sandbox() -> None:
    """Read a job on stdin, measure it here, write the result on stdout.

    Not for typing: it is what CADENCE_SANDBOX runs on the other machine,
    as in `CADENCE_SANDBOX="ssh box cadence sandbox"`.
    """
    typer.echo(answer(sys.stdin.read()))
