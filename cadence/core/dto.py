"""Every shape that crosses a boundary in cadence, in one file.

Read top to bottom, this is one trial: a Directive says what to improve, a
Completion comes back from the provider, a Proposal is what we made of it, a
Verdict is what running it was worth, an TrialResult is that pair kept for the
search, and a Report is what the user is told at the end.

They live together on purpose. When a shape changes, the thing that broke and
the thing that has to change are the same file, and `git log` on this file is
the history of cadence's contracts.

Sandbox DTOs (Job, Execution) are the exception: they stay in execution/
because Execution still interprets POSIX exit codes, and a DTO in core may not
know what a signal is.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import Field

from cadence.core.types import Frozen, Metrics, NonBlank
from cadence.core.values import Value
from cadence.core.verdict import Scored, Verdict
from cadence.lifecycle.states import RunState

__all__ = [
    "Completion",
    "Directive",
    "Proposal",
    "Recalled",
    "Report",
    "RunHistory",
    "TrialBudget",
    "TrialResult",
]


class Completion(Value):
    """What a backend gives back. Every provider converges on this shape."""

    text: str
    model: NonBlank
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)

    @property
    def cost(self) -> dict[str, float]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
        }


class Directive(Value):
    """What the search method asks the model to improve.

    It carries the trial index rather than a sentence to try, because what to
    say to a model is the prompting layer's business: a search method decides
    which parent, not which English. The index is here rather than counted by
    the model so that a resumed run asks the same question it asked before.
    """

    parent: NonBlank
    code: NonBlank
    index: int = Field(ge=0, default=0)
    inspirations: tuple[str, ...] = ()


class Proposal(Value):
    """What we made of the reply.

    Always a unified diff, whichever template asked the question, so that no
    consumer downstream has to branch on how the model chose to answer.
    """

    patch: tuple[str, ...]
    prompt: NonBlank
    recipe: Frozen[str, Any] = Field(min_length=1)
    raw_response: str

    @property
    def files_changed(self) -> int:
        return sum(1 for line in self.patch if line.startswith("+++"))


class Recalled(Value):
    """A model call we already paid for, and the prompt that earned it."""

    prompt_digest: NonBlank
    completion: Completion


class TrialResult(Value):
    """A candidate that has been measured. The unit the search reasons over."""

    code: NonBlank
    verdict: Verdict

    @property
    def metrics(self) -> Metrics | None:
        """What it scored, or None if it never got a score.

        The narrowing lives here so that callers holding an TrialResult do not
        each have to remember that a Failed verdict has no metrics.
        """
        return self.verdict.metrics if isinstance(self.verdict, Scored) else None


class RunHistory(Value):
    """Every attempt this run has made, and the programs it started from."""

    run_id: NonBlank
    seeds: tuple[NonBlank, ...] = Field(min_length=1)
    results: tuple[TrialResult, ...] = ()

    @property
    def index(self) -> int:
        return len(self.results)

    @property
    def scored(self) -> tuple[TrialResult, ...]:
        return tuple(r for r in self.results if r.verdict.is_scored)


class TrialBudget(Value):
    """What the run has spent, and what it is allowed to. Trials, not dollars."""

    spent: int = Field(ge=0)
    budget: int = Field(ge=0)

    @property
    def remaining(self) -> int:
        return max(self.budget - self.spent, 0)

    @property
    def exhausted(self) -> bool:
        return self.remaining == 0


class Report(Value):
    """What a finished run tells the user. The public output of cadence."""

    run_id: NonBlank
    status: RunState
    trials: int = Field(ge=0)
    scored: int = Field(ge=0)
    best: str | None = None
    program: str | None = None
    metrics: Mapping[str, float] | None = None
    reason: str | None = None
