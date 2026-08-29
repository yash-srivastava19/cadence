"""Reading numbers off a program's stdout.

Cadence makes no assumption about how your program is written. It makes one
about what the command prints, and this file is all of it.

Two readers, tried in order. JSON is the contract; the key-value lines are a
courtesy so that a `print(f"value: {v}")` works in a quickstart, and they will
happily match a stray log line like `progress: 0.5`. Prefer JSON.
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal, Protocol, get_args

from cadence.core.types import Metrics
from cadence.errors import MetricNotReported

__all__ = [
    "BROKE",
    "Goal",
    "JsonReport",
    "KeyValueLines",
    "MetricReader",
    "direction",
    "read",
    "verifier_broke",
]

#: How a scoring command says the fault is its own rather than the
#: candidate's. Printed on stdout, because attribution belongs in the result
#: and not in an exit code: an exit code is a thing a subprocess has, and the
#: plan is to point execution at a cluster.
#:
#:     print(json.dumps({"cadence_verifier_error": "OPENAI_API_KEY unset"}))
#:
#: Without it a broken verifier scores every candidate at the floor and the
#: run reports success, which is the one failure cadence cannot see.
BROKE = "cadence_verifier_error"

#: A real type rather than an alias for str, so a manifest saying
#: `value: maximise` is refused where it is read rather than where it is used.
Goal = Literal["minimize", "maximize"]

MINIMIZE: Goal = "minimize"
MAXIMIZE: Goal = "maximize"
GOALS: tuple[Goal, ...] = get_args(Goal)

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
REPORTED = re.compile(
    rf"^\s*(?P<name>[A-Za-z_][\w.]*)\s*[:=]\s*(?P<value>{NUMBER})\s*$"
)


def verifier_broke(stdout: str) -> str | None:
    """What the scoring command said went wrong with itself, if anything."""
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{") or BROKE not in line:
            continue
        try:
            document = json.loads(line)
        except json.JSONDecodeError:
            continue
        said = document.get(BROKE) if isinstance(document, dict) else None
        if isinstance(said, str) and said.strip():
            return said.strip()
    return None


def direction(goal: Goal) -> float:
    """+1 to maximize, -1 to minimize. The only thing a goal ever becomes."""
    if goal not in GOALS:
        raise ValueError(f"a goal is {' or '.join(GOALS)}, not {goal!r}")
    return -1.0 if goal == MINIMIZE else 1.0


class Report(Protocol):
    """One way a program might have reported its numbers."""

    def shape(self, name: str) -> str:
        """How to print that metric, for the message a silent program gets."""
        ...

    def read(self, stdout: str) -> Mapping[str, float]: ...


class JsonReport:
    """The last JSON object on stdout. The contract."""

    def shape(self, name: str) -> str:
        return f'a JSON object, like {{"{name}": 1.23}}'

    def read(self, stdout: str) -> Mapping[str, float]:
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                document = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(document, dict):
                return {
                    name: value
                    for name, value in document.items()
                    if isinstance(value, (int, float))
                }
        return {}


class KeyValueLines:
    """`name: 1.23` or `name = 1.23`, anywhere in the output."""

    def shape(self, name: str) -> str:
        return f"a line like '{name}: 1.23'"

    def read(self, stdout: str) -> Mapping[str, float]:
        found: dict[str, float] = {}
        for line in stdout.splitlines():
            match = REPORTED.match(line)
            if match:
                found[match["name"]] = float(match["value"])
        return found


DEFAULT_READERS: tuple[Report, ...] = (JsonReport(), KeyValueLines())


class MetricReader:
    """Reads the metrics a manifest asked for, or says which one is missing."""

    def __init__(
        self, wanted: Iterable[str], readers: Sequence[Report] = DEFAULT_READERS
    ) -> None:
        self.wanted = tuple(wanted)
        self.readers = tuple(readers)

    def read(self, stdout: str) -> Metrics:
        # The first reader that reports anything at all wins outright. Not
        # merged: the line reader matches a stray `progress: 0.5`, and merging
        # would let a log line overwrite the JSON a program deliberately
        # printed -- scoring candidates on noise, which is the one failure the
        # search cannot see.
        found: Mapping[str, float] = {}
        for reader in self.readers:
            found = reader.read(stdout)
            if found:
                break
        missing = [name for name in self.wanted if name not in found]
        if missing:
            raise MetricNotReported(
                f"the program never reported {', '.join(missing)}."
                f" Print {self._shapes(missing[0])} on stdout"
            )
        return {name: float(found[name]) for name in self.wanted}

    def _shapes(self, name: str) -> str:
        return ", or ".join(reader.shape(name) for reader in self.readers)


def read(stdout: str, wanted: Iterable[str]) -> Metrics:
    return MetricReader(wanted).read(stdout)
