"""The seams. Every one of these has at least two implementations, or is
about to have.

A port says what cadence needs, never what supplies it: Backend does not
mention HTTP, Objective does not mention weights, Method does not mention a
population. That is the whole reason a new provider is a row in a YAML file
and a new search strategy is one module.
"""

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from cadence.core.dto import Attempt, Completion, Directive, History, Ledger, Recalled
from cadence.core.types import Metrics

__all__ = ["Audit", "Backend", "Calls", "Method", "Objective", "Task"]


@runtime_checkable
class Backend(Protocol):
    """Somewhere a prompt can be sent. Says nothing about how."""

    @property
    def name(self) -> str: ...

    def call(self, prompt: str) -> Completion: ...


@runtime_checkable
class Audit(Protocol):
    """Somewhere every model call is reported, successful or not.

    Two methods rather than one taking an optional error: a call that
    succeeded and a call that failed are different events, and a caller that
    has to check a field to tell them apart will eventually forget.
    """

    def succeeded(self, backend: str, attempt: int) -> None: ...

    def failed(self, backend: str, attempt: int, error: Exception) -> None: ...


@runtime_checkable
class Calls(Protocol):
    """The replay store: pay for a model call once, ever."""

    def get(self, key: str) -> Recalled | None: ...

    def put(self, key: str, recalled: Recalled) -> None: ...


@runtime_checkable
class Objective(Protocol):
    """How metrics reduce to an ordering.

    `dominates`, not `compare`: an int cannot express "incomparable", which is
    the entire multi-objective case.
    """

    def dominates(self, a: Metrics, b: Metrics) -> bool: ...


@runtime_checkable
class Method(Protocol):
    """How the next thing to try gets chosen. Owns the search, nothing else."""

    def next_directive(self, history: History, ledger: Ledger) -> Directive | None: ...

    def best(self, history: History) -> Attempt | None: ...


@runtime_checkable
class Task(Protocol):
    """A problem defined in Python rather than by a command.

    Declared, unbuilt: nothing in cadence constructs one yet. The manifest
    accepts a `task` key and no code reads it.
    """

    @property
    def entry_point(self) -> str: ...

    @property
    def baseline(self) -> str: ...

    def inputs(self, seed: int) -> Sequence[Any]: ...

    def score(self, output: Any, inputs: Sequence[Any]) -> Metrics: ...
