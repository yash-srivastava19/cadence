from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cadence.verdict import Verdict

__all__ = [
    "Metrics",
    "Directive",
    "Attempt",
    "History",
    "Ledger",
    "Task",
    "Objective",
    "Method",
]

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

    def inputs(self, seed: int) -> Sequence[Any]: ...

    def score(self, output: Any, inputs: Sequence[Any]) -> Metrics: ...


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    code: NonBlank
    verdict: Verdict


class History(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    run_id: NonBlank
    seeds: tuple[NonBlank, ...] = Field(min_length=1)
    attempts: tuple[Attempt, ...] = ()

    @property
    def index(self) -> int:
        return len(self.attempts)

    @property
    def scored(self) -> tuple[Attempt, ...]:
        return tuple(a for a in self.attempts if a.verdict.is_scored)


class Ledger(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    spent: int = Field(ge=0)
    budget: int = Field(ge=0)

    @property
    def remaining(self) -> int:
        return max(self.budget - self.spent, 0)

    @property
    def exhausted(self) -> bool:
        return self.remaining == 0


@runtime_checkable
class Objective(Protocol):
    def dominates(self, a: Metrics, b: Metrics) -> bool: ...


@runtime_checkable
class Method(Protocol):
    def next_directive(self, history: History, ledger: Ledger) -> Directive | None: ...

    def best(self, history: History) -> Attempt | None: ...
