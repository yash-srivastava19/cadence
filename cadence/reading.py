import json
import re
from collections.abc import Iterable, Mapping

from cadence.exceptions import CadenceError

__all__ = ["Goal", "MetricNotReported", "direction", "read"]

Goal = str

MINIMIZE = "minimize"
MAXIMIZE = "maximize"
GOALS = (MINIMIZE, MAXIMIZE)

NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
REPORTED = re.compile(
    rf"^\s*(?P<name>[A-Za-z_][\w.]*)\s*[:=]\s*(?P<value>{NUMBER})\s*$"
)


class MetricNotReported(CadenceError):
    pass


def read(output: str, wanted: Iterable[str]) -> Mapping[str, float]:
    wanted = tuple(wanted)
    found = _from_json(output) or _from_lines(output)
    missing = [name for name in wanted if name not in found]
    if missing:
        raise MetricNotReported(
            f"the program never reported {', '.join(missing)}."
            f" Print a line like '{missing[0]}: 1.23', or a JSON object, on stdout"
        )
    return {name: float(found[name]) for name in wanted}


def direction(goal: Goal) -> float:
    if goal not in GOALS:
        raise ValueError(f"a goal is {' or '.join(GOALS)}, not {goal!r}")
    return -1.0 if goal == MINIMIZE else 1.0


def _from_json(output: str) -> dict[str, float]:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            document = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(document, dict):
            return {k: v for k, v in document.items() if isinstance(v, (int, float))}
    return {}


def _from_lines(output: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for line in output.splitlines():
        match = REPORTED.match(line)
        if match:
            found[match["name"]] = float(match["value"])
    return found
