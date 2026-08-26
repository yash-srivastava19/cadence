import shlex
from pathlib import Path

import typer

from cadence.commands.report import absent, die, found, note
from cadence.control.manifest import Manifest, load
from cadence.control.region import MarkerError, split
from cadence.control.registry import (
    METHODS,
    OBJECTIVES,
    guidance,
    objective_for,
    resolve,
    seed_program,
)
from cadence.exceptions import CadenceError
from cadence.execution.sandboxes.subprocess import Job, Subprocess
from cadence.reading import MetricNotReported, read


def check(root: Path = typer.Argument(Path("."))) -> None:
    """Check a project without spending a model call."""
    try:
        manifest = _manifest(root)
        code = _region(manifest, root)
        _plan(manifest)
        execution = _baseline(manifest, root, code)
        _metrics(manifest, execution.stdout)
        _guidance(manifest, root)
    except MetricNotReported as error:
        die(str(error))
    except CadenceError as error:
        die(str(error))
    note(f"\nready. `cadence run` will spend up to {manifest.budget.trials} trials.")


def _manifest(root: Path) -> Manifest:
    manifest = load(root)
    defaulted = len(Manifest.model_fields) - len(manifest.model_fields_set)
    found("manifest", f"{manifest.api_version}, {defaulted} defaults applied")
    return manifest


def _region(manifest: Manifest, root: Path) -> str:
    code = seed_program(manifest, root)
    markers = (manifest.markers.begin, manifest.markers.end)
    try:
        region = split(code, *markers)
    except MarkerError as error:
        die(
            f"{manifest.program}: {error}",
            f"Mark exactly one region with {markers[0]} and {markers[1]}.",
        )
    if region is None:
        die(
            f"{manifest.program} has no {markers[0]} marker, so the model's"
            " reply would replace the whole file.",
            f"Put {markers[0]} and {markers[1]} around the part to improve.",
        )
    start = region.head.count("\n") + 1
    lines = region.body.count("\n")
    found(
        "region",
        f"{manifest.program} lines {start}-{start + lines - 1}"
        f" ({lines} line{'s' if lines != 1 else ''} the model may rewrite)",
    )
    return code


def _plan(manifest: Manifest) -> None:
    objective = objective_for(manifest)
    method = resolve("method", METHODS, manifest.method, objective=objective)
    found("method", f"{manifest.method.name} built with {_options(method)}")
    found("objective", f"{_named(objective)} over {_goals(manifest)}")


def _named(objective) -> str:
    for name, kind in OBJECTIVES.items():
        if isinstance(objective, kind):
            return name
    return type(objective).__name__  # pragma: no cover


def _options(method) -> str:
    shown = {k: v for k, v in vars(method).items() if isinstance(v, (int, float, str))}
    return ", ".join(f"{k}={v}" for k, v in shown.items()) or "no options"


def _goals(manifest: Manifest) -> str:
    return ", ".join(f"{name} to {goal}" for name, goal in manifest.metrics.items())


def _baseline(manifest: Manifest, root: Path, code: str):
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
        die(
            f"`{manifest.command}` failed on your unmodified program:\n\n"
            f"{execution.stderr.strip()[-400:]}",
            "Cadence scores every candidate with this command, so it must"
            " pass before a run is worth starting.",
        )
    found(
        "baseline",
        f"`{manifest.command}` exited 0 in {execution.duration_ms:.0f}ms",
    )
    return execution


def _metrics(manifest: Manifest, stdout: str) -> None:
    readings = read(stdout, manifest.metrics)
    for name, value in readings.items():
        found("metric", f"{name} = {value:g}, and {manifest.metrics[name]} is better")
    seeds = len(manifest.sandbox.seeds)
    found(
        "sandbox",
        f"{seeds} seed{'s' if seeds != 1 else ''} per trial,"
        f" {manifest.sandbox.seconds:g}s and {manifest.sandbox.memory_mb}MB each",
    )


def _guidance(manifest: Manifest, root: Path) -> None:
    if guidance(manifest, root) is None:
        absent("guidance", f"no {manifest.guidance} — the model gets no instructions")
    else:
        found("guidance", f"{manifest.guidance} will be sent with every prompt")
