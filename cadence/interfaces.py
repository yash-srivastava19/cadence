from collections.abc import Generator, Mapping, Sequence
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, StringConstraints

from cadence.verdict import Verdict

__all__ = ["Metrics", "Directive", "Attempt", "Task", "Objective", "Method", "Search"]

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


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    code: NonBlank
    verdict: Verdict


Search = Generator[Directive, "Attempt | None", None]


@runtime_checkable
class Objective(Protocol):
    def dominates(self, a: Metrics, b: Metrics) -> bool: ...


@runtime_checkable
class Method(Protocol):
    def search(self, seeds: Sequence[str], budget: int) -> Search: ...

    def best(self) -> "Attempt | None": ...
