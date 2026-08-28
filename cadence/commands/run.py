from pathlib import Path

import typer

from cadence.commands.report import die
from cadence.control.manifest import load
from cadence.control.registry import build
from cadence.errors import CadenceError


def run(
    root: Path = typer.Argument(Path(".")),
    run_id: str = typer.Option("local", "--id"),
) -> None:
    """Improve the program named by .cadence."""
    try:
        experiment = build(load(root), root, run_id)
        report = experiment.run()
    except CadenceError as error:
        die(str(error))
        raise  # unreachable; die() exits. keeps `report` definitely bound.
    typer.echo(f"\n{report.status}  {report.scored}/{report.trials} scored")
    if report.reason:
        die(report.reason)
    if report.metrics:
        for name, value in report.metrics.items():
            typer.echo(f"  {name} = {value:g}")
        typer.echo(f"\n{report.program}")
