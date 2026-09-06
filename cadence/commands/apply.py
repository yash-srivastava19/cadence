"""Putting the winner back where it came from.

A run ends, prints the best program it found, and that was the only copy
anyone saw. `runs show` gives a fingerprint, `trials show` gives a
fingerprint; nothing returned the code. So the way to keep a result was to
not scroll past it.

This writes it to the file it is a version of.

# ponytail: no backup, no --dry-run. The file is in git and git is the undo,
# which the help text says out loud.
"""

from pathlib import Path

import typer

from cadence.commands.reading import reading
from cadence.commands.report import die, found, note
from cadence.control.manifest import load
from cadence.control.restore import winner_of
from cadence.errors import CadenceError


def apply(
    run_id: str = typer.Argument(..., metavar="RUN_ID", help="Which run's winner."),
    root: Path = typer.Argument(Path("."), help="The project to write it into."),
    config: Path | None = typer.Option(
        None,
        "--config",
        metavar="FILE",
        help="Read the manifest from FILE instead of <root>/.cadence.",
    ),
) -> None:
    """Write a run's best program over the program it improved.

    It overwrites, and keeps no backup: commit or stash first if the file
    holds anything you want back.
    """
    try:
        manifest = load(config or root)
    except CadenceError as error:
        die(str(error))
    with reading() as session:
        winner = winner_of(session, run_id)
    if winner is None:
        die(
            f"run {run_id!r} has no best program to apply.",
            "Either there is no such run, or it scored nothing. `cadence runs"
            " list` shows which runs have a best.",
        )
    # The manifest is the identity of the experiment, so applying a winner
    # into a project configured differently would write a file that was never
    # scored the way this project scores. Cheap to check, and silent to miss.
    if winner.manifest_hash and winner.manifest_hash != manifest.hash:
        die(
            f"run {run_id!r} was not run against this project's manifest.",
            "Its winner was scored under different settings, so it is not a"
            " result for this project. Use the root that run used, or"
            " --config to name the manifest it used.",
        )
    target = root / manifest.program
    target.write_text(winner.code)
    found("wrote", f"{target} from {winner.fingerprint[:12]}")
    note(f"\n`git diff {target}` to see what changed.")
