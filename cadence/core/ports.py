"""The seams. Every one of these has at least two implementations, or is
about to have.

A port says what cadence needs, never what supplies it: Backend does not
mention HTTP, Objective does not mention weights, Method does not mention a
population. That is the whole reason a new provider is a row in a YAML file
and a new search strategy is one module.
"""

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from cadence.core.dto import (
    Completion,
    Directive,
    Recalled,
    RunHistory,
    TrialBudget,
    TrialResult,
)
from cadence.core.types import Metrics

__all__ = ["Audit", "Backend", "Calls", "Locks", "Method", "Objective"]


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
class Locks(Protocol):
    """Somewhere to take a lock, so two workers do not do one piece of work.

    A lock here reduces duplicated effort and contention. It is never the
    thing that makes a double write impossible -- a lease can expire while
    its holder is still working, so every path guarded by one of these needs
    a unique constraint behind it that does not depend on timing.
    """

    def with_lock(
        self, key: str, *, ttl: float | None = None, wait: float | None = None
    ) -> AbstractContextManager[None]: ...


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

    def next_directive(
        self, history: RunHistory, ledger: TrialBudget
    ) -> Directive | None: ...

    def best(self, history: RunHistory) -> TrialResult | None: ...
