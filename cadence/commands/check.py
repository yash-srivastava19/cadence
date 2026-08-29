import shlex
from collections.abc import Mapping
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
from cadence.errors import CadenceError
from cadence.execution.sandboxes.subprocess import Job, Subprocess
from cadence.parsing.metrics import MetricNotReported, read, verifier_broke


def check(root: Path = typer.Argument(Path("."))) -> None:
    """Check a project without spending a model call."""
    try:
        manifest = _manifest(root)
        code = _region(manifest, root)
        _plan(manifest)
        execution = _baseline(manifest, root, code)
        readings = _metrics(manifest, execution.stdout)
        _repeats(manifest, root, code, readings)
        _affordable(manifest, execution)
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


def _score_once(manifest: Manifest, root: Path, code: str):
    return Subprocess().run(
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


def _baseline(manifest: Manifest, root: Path, code: str):
    execution = _score_once(manifest, root, code)
    broke = verifier_broke(execution.stdout)
    if broke is not None:
        die(
            f"`{manifest.command}` reported a fault of its own: {broke}",
            "A scoring command already broken before a run starts would score"
            " every candidate the same way, and the run would report success.",
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


def _metrics(manifest: Manifest, stdout: str) -> Mapping[str, float]:
    readings = read(stdout, manifest.metrics)
    for name, value in readings.items():
        found("metric", f"{name} = {value:g}, and {manifest.metrics[name]} is better")
    seeds = len(manifest.sandbox.seeds)
    found(
        "sandbox",
        f"{seeds} seed{'s' if seeds != 1 else ''} per trial,"
        f" {manifest.sandbox.seconds:g}s and {manifest.sandbox.memory_mb}MB each",
    )
    return readings


def _repeats(manifest: Manifest, root: Path, code: str, first: Mapping[str, float]):
    """Score the unmodified program a second time and compare.

    A scoring rule that answers differently each time makes the search chase
    noise: a candidate is admitted for being lucky, and the run reports a
    winner nobody can reproduce. It is the cheapest of the silent failures to
    catch -- one more run of a program that has already run once.

    A tolerance rather than exact equality, because exact only holds for small
    integer programs. Anything with float reduction order or threads differs
    in the last places without being meaningfully non-deterministic, and the
    manifest is where a project says how much of that it has.
    """
    again = _score_once(manifest, root, code)
    if not again.ok:
        die(
            f"`{manifest.command}` passed once and failed the second time.",
            "Cadence runs it once per seed per trial. One that fails"
            " intermittently cannot rank anything.",
        )
    second = read(again.stdout, manifest.metrics)
    tolerance = manifest.verifier.tolerance
    drifted = {
        name: (first[name], second[name])
        for name in first
        if abs(first[name] - second[name]) > (tolerance or 0.0)
    }
    if not drifted:
        if tolerance is None:
            absent(
                "repeatable",
                "scored the same twice, and nothing declares it -- set"
                " verifier.tolerance to let cadence reuse a score",
            )
        else:
            found("repeatable", f"scored the same twice, within {tolerance:g}")
        return
    named = ", ".join(
        f"{name} {was:g} then {now:g}" for name, (was, now) in drifted.items()
    )
    if tolerance is None:
        absent("repeatable", f"scored differently the second time: {named}")
        note(
            "\nThe search will chase that noise: a candidate is admitted for"
            "\nbeing lucky, and the run reports a winner you cannot reproduce."
        )
        return
    die(
        f"the same program scored differently twice: {named}",
        f"verifier.tolerance says {tolerance:g} and this is outside it."
        " Either the scoring rule is not repeatable or the tolerance is wrong.",
    )


def _affordable(manifest: Manifest, execution) -> None:
    """What the run will spend scoring, at this speed.

    One run is quick and five hundred are not. Projecting it costs nothing and
    is the difference between finding out now and finding out in six hours.
    """
    seeds = len(manifest.sandbox.seeds)
    total = execution.duration_ms * seeds * manifest.budget.trials / 1000
    spent = f"{total / 60:.0f} minutes" if total >= 90 else f"{total:.0f}s"
    found(
        "cost",
        f"{manifest.budget.trials} trials x {seeds} seeds x"
        f" {execution.duration_ms:.0f}ms is about {spent} of scoring",
    )
    if total >= 3600:
        note(
            f"\nThat is {total / 3600:.1f} hours before a model call is counted."
            "\nFewer seeds, fewer trials or a faster command would all help."
        )


def _guidance(manifest: Manifest, root: Path) -> None:
    if guidance(manifest, root) is None:
        absent("guidance", f"no {manifest.guidance} — the model gets no instructions")
    else:
        found("guidance", f"{manifest.guidance} will be sent with every prompt")
