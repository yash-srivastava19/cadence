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
from datetime import datetime
from typing import Any, NamedTuple

from pydantic import Field

from cadence.core.types import Frozen, Metrics, NonBlank
from cadence.core.values import Value
from cadence.core.verdict import Scored, Verdict
from cadence.lifecycle.states import RunState, TrialState

__all__ = [
    "Completion",
    "Directive",
    "ExperimentSummary",
    "Measurement",
    "Proposal",
    "Recalled",
    "RecordedManifest",
    "Report",
    "Request",
    "RunDetail",
    "RunHistory",
    "RunSummary",
    "Spend",
    "Suggestion",
    "TrialBudget",
    "TrialDetail",
    "TrialResult",
    "TrialSummary",
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


class SchemaState(Value):
    """What a database is, as far as cadence is concerned."""

    #: host:port/database. Printed, so never the password.
    where: NonBlank
    at: str | None
    head: NonBlank
    expected: NonBlank
    pending: tuple[str, ...] = ()
    app_role: bool = False

    @property
    def is_current(self) -> bool:
        return self.at == self.expected


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
    """What the model layer hands back: the proposal, and whether the answer
    was read back out of the replay store rather than bought.

    A tuple rather than a Value because the caller unpacks it. Only the
    proposal and `replayed` are ever read: Experiment reports the call where
    the answer arrives, before there is a Suggestion to report from, and the
    completion it holds is the caller's already.
    """

    proposal: Proposal
    replayed: bool = False


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

    def called(self) -> "Spend":
        """One more ask, not yet answered.

        Counted at ModelRequested, before the call: a request the provider
        never answered was still made, and that is what `calls` counts. It
        takes this many prompts to reproduce the run however they ended.
        """
        return self.model_copy(update={"calls": self.calls + 1})

    def answered(
        self,
        tokens_in: int,
        tokens_out: int,
        replayed: bool,
        usd: float | None = None,
    ) -> "Spend":
        """The bill from an answer. Never counts another ask: the ask was
        already counted at ModelRequested.

        None rather than 0.0 for a replayed answer: adding a zero would turn
        "nothing was bought" into a stated bill of $0.00, and a run that
        replayed everything did not buy nothing for free -- it did not buy.
        """
        return self.model_copy(
            update={
                "replayed": self.replayed + int(replayed),
                "tokens_in": self.tokens_in + tokens_in,
                "tokens_out": self.tokens_out + tokens_out,
                # None until something priced arrives, rather than zero, because a
                # run against a provider nobody priced has not spent nothing -- it
                # has spent an amount cadence cannot name, and saying $0.00 would
                # be a lie with a decimal point on it.
                "usd": self._plus(None if replayed else usd),
            }
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


class RunSummary(Value):
    """A run as the database remembers it.

    Not a Report: a Report is what a run that just ended says about itself,
    and it can hold the winning program. A listing of four hundred runs
    cannot.
    """

    id: NonBlank
    status: RunState
    trials: int = Field(ge=0)
    # Null for runs recorded before cadence wrote these down.
    owner: str | None = None
    experiment: str | None = None
    best: str | None = None
    reason: str | None = None
    started_at: datetime | None = None
    #: Says RUNNING and has not written anything in a long time. Derived when
    #: the row is read, not stored: no column, no migration, and a run that
    #: comes back to life stops being stalled without anyone updating it.
    stalled: bool = False


class TrialSummary(Value):
    """One trial, as the database remembers it."""

    id: NonBlank
    run_id: NonBlank
    seq: int = Field(ge=0)
    status: TrialState
    attempts: int = Field(ge=0)
    parent: str | None = None
    candidate: str | None = None
    # What running it was worth. Null until it has been run, and for good if
    # the patch never applied -- an abandoned trial produced nothing to score.
    outcome: str | None = None
    metrics: Mapping[str, float] | None = None
    reason: str | None = None
    started_at: datetime | None = None


class RunDetail(RunSummary):
    """One run, with the numbers a listing cannot afford to carry.

    A subclass rather than a sibling: everything the listing says about a run
    is still true on its own page, and a reader who has learned one shape has
    learned both. What it adds is the two joins a fifty-row listing will not
    pay for -- what the run spent, and how long it took.
    """

    scored: int = Field(default=0, ge=0)
    spend: Spend = Spend()
    #: From the first fact to the last, because runs have no finished_at: a
    #: killed process writes no terminal row, and the tape is the only clock
    #: that agrees with what actually happened.
    duration_ms: float | None = None
    cap_trials: int | None = None
    cap_usd: float | None = None
    #: The .cadence this run was started from, verbatim. The point of a run
    #: page is to answer "what was I even trying", and the hash cannot.
    manifest: str | None = None


class TrialDetail(TrialSummary):
    """One trial, with what it cost and what it changed.

    The diff is assembled here rather than stored: both programs are already
    in blobs, keyed by content, and a diff computed on the way out is one
    that can never disagree with the two blobs it came from.
    """

    wall_ms: float | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    #: Parent source against candidate source, unified. None when the patch
    #: never applied, which is a different answer from an empty diff: one
    #: trial changed nothing, the other produced nothing to compare.
    diff: str | None = None
    code: str | None = None


class ExperimentSummary(Value):
    """Every run that named the same experiment, rolled up.

    Derived, not stored. There is no experiments table -- `experiment` is a
    column runs copy off their manifest -- so this is a GROUP BY with a name,
    and it can only ever say what its runs say.
    """

    name: str
    runs: int = Field(ge=0)
    running: int = Field(default=0, ge=0)
    best: str | None = None
    last_activity: datetime | None = None
