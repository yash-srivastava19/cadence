from collections.abc import Mapping
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, StringConstraints

__all__ = ["Metrics", "Directive", "Task", "Objective"]

Metrics = Mapping[str, float]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Directive(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    parent: NonBlank
    code: NonBlank
    hint: NonBlank
    inspirations: tuple[str, ...] = ()


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
