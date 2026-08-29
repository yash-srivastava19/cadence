"""What has to be true before a run is worth starting.

Split in two, because the two halves cost different things:

    inspect()   reads files and builds objects. Free, and no side effects.
    rehearse()  runs the user's program. One subprocess, and the only way to
                learn whether the scoring command works at all.

`cadence run` calls inspect() and `cadence check` calls both. That is a
decision rather than an oversight: the cheap half catches the failures a run
would otherwise discover by producing garbage -- an unmarked program whose
whole contents get replaced, a method that does not exist, a metric name
nothing reports -- and it costs a run nothing to hold itself to it. Making
`run` also rehearse would spend a subprocess, and for a verifier that takes
forty seconds and calls an API, that is a real bill for re-learning what
check already said.

Findings come back rather than being printed. A function that reads a file
should not be deciding whether the process exits, and a command is not the
only thing that will ever want to ask.
"""

from collections.abc import Sequence
from pathlib import Path

from cadence.control.manifest import Manifest
from cadence.control.region import split
from cadence.control.registry import METHODS, OBJECTIVES, objective_for, resolve
from cadence.core.types import NonBlank
from cadence.core.values import Value
from cadence.errors import CadenceError

__all__ = ["Finding", "Preflight", "inspect"]


class Finding(Value):
    """One thing that was checked, and what was found."""

    about: NonBlank
    detail: NonBlank
    ok: bool = True
    fix: str | None = None


class Preflight(Value):
    findings: tuple[Finding, ...] = ()

    @property
    def ready(self) -> bool:
        return all(finding.ok for finding in self.findings)

    @property
    def wrong(self) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if not finding.ok)


def inspect(manifest: Manifest, root: Path, code: str) -> Preflight:
    """Everything that can be known without running anything."""
    return Preflight(findings=tuple(_looked_at(manifest, root, code)))


def _looked_at(manifest: Manifest, root: Path, code: str) -> Sequence[Finding]:
    return [
        _the_manifest(manifest),
        _the_region(manifest, code),
        _the_method(manifest),
    ]


def _the_manifest(manifest: Manifest) -> Finding:
    defaulted = len(Manifest.model_fields) - len(manifest.model_fields_set)
    return Finding(
        about="manifest",
        detail=f"{manifest.api_version}, {defaulted} defaults applied",
    )


def _the_region(manifest: Manifest, code: str) -> Finding:
    markers = (manifest.markers.begin, manifest.markers.end)
    try:
        region = split(code, *markers)
    except CadenceError as error:
        return Finding(
            about="region",
            detail=f"{manifest.program}: {error}",
            ok=False,
            fix=f"Mark exactly one region with {markers[0]} and {markers[1]}.",
        )
    if region is None:
        return Finding(
            about="region",
            detail=(
                f"{manifest.program} has no {markers[0]} marker, so the"
                " model's reply would replace the whole file"
            ),
            ok=False,
            fix=f"Put {markers[0]} and {markers[1]} around the part to improve.",
        )
    start = region.head.count("\n") + 1
    lines = region.body.count("\n")
    return Finding(
        about="region",
        detail=(
            f"{manifest.program} lines {start}-{start + lines - 1}"
            f" ({lines} line{'s' if lines != 1 else ''} the model may rewrite)"
        ),
    )


def _the_method(manifest: Manifest) -> Finding:
    try:
        method = resolve(
            "method", METHODS, manifest.method, objective=objective_for(manifest)
        )
    except CadenceError as error:
        return Finding(about="method", detail=str(error), ok=False)
    shown = {k: v for k, v in vars(method).items() if isinstance(v, (int, float, str))}
    options = ", ".join(f"{k}={v}" for k, v in shown.items()) or "no options"
    return Finding(
        about="method", detail=f"{manifest.method.name} built with {options}"
    )


def named(objective) -> str:
    for name, kind in OBJECTIVES.items():
        if isinstance(objective, kind):
            return name
    return type(objective).__name__  # pragma: no cover
