from collections.abc import Mapping

from pydantic import Field

from cadence.core.dto import RecordedManifest
from cadence.core.types import NonBlank
from cadence.core.verdict import Verdict
from cadence.lifecycle.states import RunState
from cadence.observe.channel import Channel, Fact

__all__ = [
    "Event",
    "ModelCalled",
    "PatchRejected",
    "ProposalReceived",
    "RunFinished",
    "RunStarted",
    "TrialAbandoned",
    "TrialMeasured",
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
    budget: Mapping[str, float] = Field(default_factory=dict)


class RunFinished(Event):
    # How it ended, not just that it did: a reader of the tape should not have
    # to infer "failed" from the absence of a best.
    status: RunState
    trials: int = Field(ge=0)
    best: str | None = None
    reason: str | None = None


class TrialStarted(Event):
    trial_id: NonBlank
    parent: str | None = None


class ModelCalled(Event):
    trial_id: NonBlank
    backend: NonBlank
    replayed: bool = False
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class ProposalReceived(Event):
    trial_id: NonBlank
    files_changed: int = Field(ge=0)


class PatchRejected(Event):
    trial_id: NonBlank
    reason: NonBlank


class TrialMeasured(Event):
    trial_id: NonBlank
    verdict: Verdict


class TrialAbandoned(Event):
    trial_id: NonBlank
    reason: NonBlank
