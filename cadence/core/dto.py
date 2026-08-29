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
from typing import Any, NamedTuple

from pydantic import Field

from cadence.core.types import Frozen, Metrics, NonBlank
from cadence.core.values import Value
from cadence.core.verdict import Scored, Verdict
from cadence.lifecycle.states import RunState

__all__ = [
    "Completion",
    "Directive",
    "Measurement",
    "Proposal",
    "Recalled",
    "RecordedManifest",
    "Report",
    "Request",
    "RunHistory",
    "Spend",
    "Suggestion",
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
    #: What it cost, when a price for this model was declared. None means
    #: nobody said, which is different from free -- and only the backend that
    #: made the call is in a position to know which.
    cost_usd: float | None = Field(default=None, ge=0)

    @property
    def cost(self) -> dict[str, float | None]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
        }


class RecordedManifest(Value):
    """The configuration a run was started from, as it will be written down.

    The text as well as the hash: a hash tells you two runs used the same
    configuration, and only the text tells you what that configuration said.
    """

    hash: NonBlank
    source: NonBlank
    api_version: NonBlank


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
    #: What the parent scored, or None for a seed nobody has measured. The
    #: numbers only: which way is better is the manifest's, and saying so in
    #: English is the prompting layer's.
    standing: Frozen[str, float] | None = None


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


class Request(Value):
    """A model call that has been built but not yet made.

    The half of asking a model that costs nothing: the prompt is rendered,
    the recipe that rebuilds it is fixed, and the replay key is decided. It
    exists so that all of that can be written down before the call is made,
    which is the only way a restart can tell "about to pay" from "never
    started".
    """

    key: NonBlank
    prompt: NonBlank
    digest: NonBlank
    recipe: Frozen[str, Any] = Field(min_length=1)
    #: The template this was rendered from, by content. The recipe names the
    #: template; the body of it lives in code that changes, so a run replayed
    #: after an edit would rebuild a different prompt without this.
    template_hash: NonBlank = "unknown"


class Suggestion(NamedTuple):
    """What the model layer hands back: the proposal, and what it cost.

    A tuple rather than a Value because `Model.send` and `Model.propose`
    unpack all of it, and because `replayed` is a fact about this call rather
    than about the proposal -- the same proposal replayed is the same
    proposal. Experiment takes only the proposal: it reports the call where
    the answer arrives, which is before there is a Suggestion to report from.
    """

    proposal: Proposal
    completion: Completion
    replayed: bool = False
    #: Which request this answers. Empty when nobody asked for one by key.
    key: str = ""


class Recalled(Value):
    """A model call we already paid for, and the prompt that earned it."""

    prompt_digest: NonBlank
    completion: Completion


class Measurement(Value):
    """What running a candidate turned out to be, and how long it took.

    The time is not part of the verdict: two runs of one program that score
    the same are the same verdict however long they took, and the verdict is
    keyed on being the same. It travels beside it instead.
    """

    verdict: Verdict
    wall_ms: float = Field(ge=0, allow_inf_nan=False)


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


class Spend(Value):
    """What a run cost: the work in tokens, and the bill in dollars.

    Dollars only when a price was declared. Cadence ships no prices for paid
    providers -- one is a fact about someone else's catalogue that goes stale
    without telling anyone -- so the number comes from the user's own
    providers.local.yml or it does not come at all. A price the user wrote is
    a price they can see the age of; a price cadence shipped is one they
    cannot, which is why `usd` is None far more often than it is zero.

    The two count different things on purpose. `calls` and `tokens` are the
    work the run asked for, replays included, because that is what it takes
    to reproduce. `usd` is what this run was billed, replays excluded,
    because an answer read back out of the database was not bought again.
    """

    calls: int = Field(default=0, ge=0)
    replayed: int = Field(default=0, ge=0)
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    usd: float | None = Field(default=None, ge=0)

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def and_also(
        self,
        tokens_in: int,
        tokens_out: int,
        replayed: bool,
        usd: float | None = None,
    ) -> "Spend":
        return Spend(
            calls=self.calls + 1,
            replayed=self.replayed + int(replayed),
            tokens_in=self.tokens_in + tokens_in,
            tokens_out=self.tokens_out + tokens_out,
            # None rather than 0.0 for a replay: adding a zero would turn
            # "nothing was bought" into a stated bill of $0.00, and a run
            # that replayed everything did not buy nothing for free -- it
            # did not buy.
            usd=self._plus(None if replayed else usd),
        )

    def _plus(self, usd: float | None) -> float | None:
        """None and zero are different answers, so they add differently.

        None until something priced arrives, rather than zero, because a run
        against a provider nobody priced has not spent nothing -- it has spent
        an amount cadence cannot name, and saying $0.00 would be a lie with a
        decimal point on it. A run holds one backend, so in practice every
        call is priced or none is.
        """
        if usd is None:
            return self.usd
        return usd + (self.usd or 0.0)


class Report(Value):
    """What a finished run tells the user. The public output of cadence."""

    run_id: NonBlank
    status: RunState
    trials: int = Field(ge=0)
    scored: int = Field(ge=0)
    spend: Spend = Spend()
    best: str | None = None
    program: str | None = None
    metrics: Mapping[str, float] | None = None
    reason: str | None = None
