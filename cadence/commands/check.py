import shlex
from pathlib import Path

import typer

from cadence.commands.report import die, missing, said
from cadence.control.manifest import load
from cadence.control.registry import METHODS, OBJECTIVES, guidance, seed_program
from cadence.exceptions import CadenceError
from cadence.execution.sandboxes.subprocess import Job, Subprocess
from cadence.reading import MetricNotReported, read


def check(root: Path = typer.Argument(Path("."))) -> None:
    """Fail in seconds for the reasons a run fails in hours."""
    try:
        manifest = load(root)
        said(".cadence")

        if manifest.method.name not in METHODS:
            die(f"no method named {manifest.method.name!r}")
        if manifest.objective and manifest.objective.name not in OBJECTIVES:
            die(f"no objective named {manifest.objective.name!r}")
        said(f"method {manifest.method.name}")

        code = seed_program(manifest, root)
        said(manifest.program)

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
        said(f"{manifest.command}   {execution.duration_ms:.0f}ms")

        for name, value in read(execution.stdout, manifest.metrics).items():
            said(f"{name} = {value:g}   ({manifest.metrics[name]})")

        if guidance(manifest, root) is None:
            missing(manifest.guidance)
        typer.echo(f"\nready. {manifest.budget.trials} trials.")
    except MetricNotReported as error:
        die(str(error))
    except CadenceError as error:
        die(str(error))
