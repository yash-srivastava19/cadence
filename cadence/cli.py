import shlex
from pathlib import Path

import typer

from cadence.exceptions import CadenceError
from cadence.manifest import load
from cadence.reading import MetricNotReported, read
from cadence.registry import METHODS, OBJECTIVES, build, guidance, seed_program
from cadence.sandbox import Job, Subprocess

app = typer.Typer(add_completion=False, help="Improve a program you already wrote.")

OK = "  ok      "
BAD = "  failed  "


def die(message: str) -> None:
    typer.echo(f"\n{message}", err=True)
    raise typer.Exit(1)


@app.command()
def check(root: Path = typer.Argument(Path("."))) -> None:
    """Fail in seconds for the reasons a run fails in hours."""
    try:
        manifest = load(root)
        typer.echo(f"{OK}.cadence")

        if manifest.method.name not in METHODS:
            die(f"no method named {manifest.method.name!r}")
        if manifest.objective and manifest.objective.name not in OBJECTIVES:
            die(f"no objective named {manifest.objective.name!r}")
        typer.echo(f"{OK}method {manifest.method.name}")

        code = seed_program(manifest, root)
        typer.echo(f"{OK}{manifest.program}")

        execution = Subprocess().run(
            Job(
                code=code,
                program=manifest.program,
                command=tuple(shlex.split(manifest.command)),
                workspace=str(root),
                seed=manifest.sandbox.seeds[0],
                seconds=manifest.sandbox.seconds,
                memory_mb=manifest.sandbox.memory_mb,
            )
        )
        if not execution.ok:
            die(f"{manifest.command} failed:\n{execution.stderr.strip()[-400:]}")
        typer.echo(f"{OK}{manifest.command}   {execution.duration_ms:.0f}ms")

        baseline = read(execution.stdout, manifest.metrics)
        for name, value in baseline.items():
            typer.echo(f"{OK}{name} = {value:g}   ({manifest.metrics[name]})")

        if guidance(manifest, root) is None:
            typer.echo(f"  absent  {manifest.guidance}")
        typer.echo(f"\nready. {manifest.budget.trials} trials.")
    except MetricNotReported as error:
        die(str(error))
    except CadenceError as error:
        die(str(error))


@app.command()
def run(
    root: Path = typer.Argument(Path(".")),
    run_id: str = typer.Option("local", "--id"),
) -> None:
    """Improve the program named by .cadence."""
    try:
        manifest = load(root)
        experiment = build(manifest, root, run_id)
    except CadenceError as error:
        die(str(error))

    report = experiment.run()
    typer.echo(f"\n{report.status}  {report.scored}/{report.trials} scored")
    if report.reason:
        die(report.reason)
    if report.metrics:
        for name, value in report.metrics.items():
            typer.echo(f"  {name} = {value:g}")
        typer.echo(f"\n{report.program}")


@app.command()
def schema() -> None:
    """Print the JSON Schema for .cadence."""
    import json

    from cadence.manifest import Manifest

    typer.echo(json.dumps(Manifest.model_json_schema(), indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
