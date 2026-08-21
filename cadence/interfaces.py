from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

__all__ = ["Metrics", "Task", "Objective"]

Metrics = Mapping[str, float]


@runtime_checkable
class Task(Protocol):
    @property
    def entry_point(self) -> str: ...

    @property
    def baseline(self) -> str: ...

    def inputs(self, seed: int) -> Any: ...

    def score(self, output: Any, inputs: Any) -> Metrics: ...


@runtime_checkable
class Objective(Protocol):
    def dominates(self, a: Metrics, b: Metrics) -> bool: ...
