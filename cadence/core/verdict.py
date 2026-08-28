from collections.abc import Mapping
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
)

__all__ = [
    "FAILURES",
    "FINGERPRINT_LENGTH",
    "Failed",
    "Outcome",
    "Proposal",
    "Scored",
    "Verdict",
    "fingerprint",
]

FINGERPRINT_LENGTH = 16


def fingerprint(code: str) -> str:
    return sha256(code.encode()).hexdigest()[:FINGERPRINT_LENGTH]


K = TypeVar("K")
V = TypeVar("V")


def _freeze(value: Mapping) -> Mapping:
    return MappingProxyType(dict(value))


Frozen = Annotated[Mapping[K, V], AfterValidator(_freeze), PlainSerializer(dict)]
Metric = Annotated[float, Field(allow_inf_nan=False)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Outcome(StrEnum):
    SCORED = "scored"
    INVALID = "invalid"
    CRASHED = "crashed"
    TIMED_OUT = "timed_out"
    OUT_OF_MEMORY = "out_of_memory"
    VERIFIER_ERROR = "verifier_error"


FAILURES = tuple(o for o in Outcome if o is not Outcome.SCORED)


class _Verdict(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    fingerprint: NonBlank

    @property
    def is_scored(self) -> bool:
        return self.outcome is Outcome.SCORED

    @property
    def escalates(self) -> bool:
        return self.outcome is Outcome.VERIFIER_ERROR


class Scored(_Verdict):
    outcome: Literal[Outcome.SCORED] = Outcome.SCORED
    metrics: Frozen[str, Metric] = Field(min_length=1)


class Failed(_Verdict):
    outcome: Literal[*FAILURES]
    reason: NonBlank


Verdict = Annotated[Scored | Failed, Field(discriminator="outcome")]


class Proposal(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    patch: tuple[str, ...]
    prompt: NonBlank
    recipe: Frozen[str, Any] = Field(min_length=1)
    raw_response: str
