import shlex
from pathlib import Path

from cadence.backends import Scripted, known, served
from cadence.exceptions import CadenceError
from cadence.experiment import Experiment
from cadence.manifest import Manifest, Plugin
from cadence.methods import Evolution
from cadence.model import Model
from cadence.objectives import Pareto, WeightedSum
from cadence.reading import direction
from cadence.runner import TrialRunner
from cadence.sandbox import Subprocess

__all__ = ["METHODS", "OBJECTIVES", "BACKENDS", "Unknown", "build", "seed_program"]


class Unknown(CadenceError):
    pass


def _make(name: str):
    def build(**options):
        return served(name, **options)

    return build


METHODS = {"evolution": Evolution}
OBJECTIVES = {"weighted_sum": WeightedSum, "pareto": Pareto}
BACKENDS = {"scripted": Scripted, **{name: _make(name) for name in known()}}


def resolve(kind: str, known: dict, plugin: Plugin, **extra):
    if plugin.name not in known:
        raise Unknown(
            f"no {kind} named {plugin.name!r}; known {kind}s: {', '.join(sorted(known))}"
        )
    return known[plugin.name](**extra, **plugin.options)


def objective_for(manifest: Manifest):
    if manifest.objective is not None:
        return resolve("objective", OBJECTIVES, manifest.objective)
    weights = {name: direction(goal) for name, goal in manifest.metrics.items()}
    return WeightedSum(**weights)


def seed_program(manifest: Manifest, root: Path) -> str:
    path = root / manifest.program
    if not path.exists():
        raise Unknown(f"{manifest.program} does not exist in {root}")
    return path.read_text()


def guidance(manifest: Manifest, root: Path) -> str | None:
    path = root / manifest.guidance
    return path.read_text() if path.exists() else None


def build(manifest: Manifest, root: Path, run_id: str, backend=None) -> Experiment:
    return Experiment(
        run_id=run_id,
        method=resolve(
            "method", METHODS, manifest.method, objective=objective_for(manifest)
        ),
        model=Model(
            backend=backend or resolve("backend", BACKENDS, manifest.model),
            markers=(manifest.markers.begin, manifest.markers.end),
        ),
        runner=TrialRunner(
            program=manifest.program,
            command=shlex.split(manifest.command),
            metrics=manifest.metrics,
            sandbox=Subprocess(),
            workspace=str(root),
            seeds=manifest.sandbox.seeds,
            seconds=manifest.sandbox.seconds,
            memory_mb=manifest.sandbox.memory_mb,
        ),
        seeds=[seed_program(manifest, root)],
        budget=manifest.budget.trials,
    )
