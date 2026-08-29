from collections.abc import Mapping
from typing import Any

from pydantic import Field

from cadence.core.dto import RecordedManifest
from cadence.core.types import NonBlank
from cadence.core.verdict import Verdict
from cadence.lifecycle.states import RunState
from cadence.observe.channel import Channel, Fact

__all__ = [
    "CandidateBuilt",
    "Event",
    "ModelCalled",
    "ModelRequested",
    "PatchRejected",
    "ProposalReceived",
    "RunFinished",
    "RunResumed",
    "RunStarted",
    "TrialAbandoned",
    "TrialMeasured",
    "TrialRetried",
    "TrialStarted",
    "cadence",
]

cadence = Channel("cadence")


class Event(Fact, channel=cadence):
    run_id: NonBlank


class RunStarted(Event):
    method: NonBlank
    # Which configuration produced this run. Every result is read against it,
    # and the tape carries the text so a stored run explains itself.
    manifest: RecordedManifest
    # The programs the search starts from. On the tape because they are the
    # ancestors of every candidate, and lineage that starts nowhere is not
    # lineage.
    seeds: tuple[NonBlank, ...] = ()
    budget: Mapping[str, float] = Field(default_factory=dict)


class RunResumed(Event):
    """This run was already under way and is being picked up again.

    Not a second RunStarted: the run row exists, the tape has facts on it
    already, and a start that happened twice would be two accounts of one
    thing. What is worth saying is where it is picking up from.
    """

    trials: int = Field(ge=0)
    results: int = Field(ge=0)


class RunFinished(Event):
    # How it ended, not just that it did: a reader of the tape should not have
    # to infer "failed" from the absence of a best.
    status: RunState
    trials: int = Field(ge=0)
    best: str | None = None
    reason: str | None = None


class TrialStarted(Event):
    trial_id: NonBlank
    # Where this trial sits in its run. The same number the trials table is
    # unique on, so the tape and the table agree without either counting.
    seq: int = Field(ge=0)
    parent: str | None = None


class ModelRequested(Event):
    """We are about to call a model, and here is exactly what we will ask.

    Emitted before the call, and recorded before it is made. Everything else
    in a trial happens inside our own process, where dying means it either
    happened or it did not and a restart can tell. A model call is the one
    step where dying leaves the question open -- so it is written down first,
    and a restart that finds a request with no answer knows it may already
    have been paid for.

    The recipe is what makes that useful: it has to rebuild this prompt byte
    for byte, or a replayed answer is an answer to a different question.
    """

    trial_id: NonBlank
    backend: NonBlank
    key: NonBlank
    prompt_digest: NonBlank
    recipe: Mapping[str, Any]


class ModelCalled(Event):
    trial_id: NonBlank
    backend: NonBlank
    # Which request this answers, so a recorded call has a question.
    key: NonBlank
    # And what came back. Stored, so a run picked up again hands the answer
    # over instead of buying it twice. Kept out of the event payload for the
    # same reason the program is: it is large, and events may not be pruned.
    response: str
    model: NonBlank
    replayed: bool = False
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class ProposalReceived(Event):
    trial_id: NonBlank
    files_changed: int = Field(ge=0)


class TrialRetried(Event):
    """The reply could not be used, and the trial is asking again.

    Separate from PatchRejected because they used to be the same fact meaning
    two different things -- one costs a model call, the other ends the trial --
    and a tape you cannot tell them apart on cannot say what happened.
    """

    trial_id: NonBlank
    reason: NonBlank


class PatchRejected(Event):
    """The diff would not apply, even after recount. The trial is unusable."""

    trial_id: NonBlank
    reason: NonBlank


class CandidateBuilt(Event):
    """The patch applied, and this program is what came out.

    Carries the source itself, once: the journal puts it in blobs, keyed by
    content, and keeps only the fingerprint on the tape.
    """

    trial_id: NonBlank
    fingerprint: NonBlank
    code: NonBlank
    parent: str | None = None


class TrialMeasured(Event):
    trial_id: NonBlank
    verdict: Verdict
    # What it was measured against. On the fact rather than looked up later,
    # so a verdict on the tape says what it is a verdict about -- and so the
    # three of them together are the key the verdicts table is stored under.
    task_hash: NonBlank
    seeds_hash: NonBlank


class TrialAbandoned(Event):
    trial_id: NonBlank
    reason: NonBlank
