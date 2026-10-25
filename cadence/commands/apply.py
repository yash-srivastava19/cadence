"""Putting the winner back where it came from.

A run ends, prints the best program it found, and that was the only copy
anyone saw. `runs show` gives a fingerprint, `trials show` gives a
fingerprint; nothing returned the code. So the way to keep a result was to
not scroll past it.

This writes it to the file it is a version of.

# ponytail: no backup, no --dry-run. The file is in git and git is the undo,
# which the help text says out loud.
"""

import json
import os
from pathlib import Path

import typer

from cadence.commands.reading import reading
from cadence.commands.report import die, found, note
from cadence.control.manifest import load
from cadence.control.restore import Winner, winner_of
from cadence.delivery.runlog import find_result
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
    # The database is the record when there is one; the file beside the log
    # is what a run without one leaves behind.
    if os.environ.get("DATABASE_URL"):
        with reading() as session:
            winner = winner_of(session, run_id)
    else:
        kept = find_result(root, run_id)
        winner = _from_file(kept) if kept else None
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
    # Stored code is stripped; the file keeps its own last newline.
    ends = "\n" if target.read_text().endswith("\n") else ""
    target.write_text(winner.code.rstrip("\n") + ends)
    found("wrote", f"{target} from {winner.fingerprint[:12]}")
    note(f"\n`git diff {target}` to see what changed.")


def _from_file(path: Path) -> Winner | None:
    """The winner a run left beside its log, so applying needs no database."""
    report = json.loads(path.read_text())
    if not report.get("program"):
        return None
    return Winner(
        code=report["program"],
        fingerprint=report["best"],
        manifest_hash=report.get("manifest_hash"),
    )
