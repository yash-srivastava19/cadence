"""What a candidate turned out to be.

One float cannot carry four facts. A single score column forces "did it run",
"is it valid", "how good" and "why did it fail" through one number, which is
how sentinels like 1e8 get invented. A verdict is either Scored, and has
metrics, or Failed, and has a reason. Nothing has both, and nothing has
neither -- which is what lets a caller read `.metrics` without a guard.
"""

from enum import StrEnum
from typing import Annotated, Literal, get_args

from pydantic import Field

from cadence.core.types import Frozen, Metric, NonBlank
from cadence.core.values import Value

__all__ = ["FAILURES", "Failed", "Failure", "Outcome", "Scored", "Verdict"]


class Outcome(StrEnum):
    SCORED = "scored"
    INVALID = "invalid"
    CRASHED = "crashed"
    TIMED_OUT = "timed_out"
    OUT_OF_MEMORY = "out_of_memory"
    VERIFIER_ERROR = "verifier_error"


#: Every outcome that is not a score. Spelled out rather than unpacked from
#: FAILURES: a Literal built by a comprehension is a type no checker can read.
Failure = Literal[
    Outcome.INVALID,
    Outcome.CRASHED,
    Outcome.TIMED_OUT,
    Outcome.OUT_OF_MEMORY,
    Outcome.VERIFIER_ERROR,
]

FAILURES = tuple(outcome for outcome in Outcome if outcome is not Outcome.SCORED)

assert set(get_args(Failure)) == set(FAILURES), "Failure and Outcome disagree"


class _Verdict(Value):
    # Declared here, narrowed by each subclass. Without it the two properties
    # below read an attribute the base does not have, which every type checker
    # is right to complain about.
    outcome: Outcome
    fingerprint: NonBlank

    @property
    def is_scored(self) -> bool:
        return self.outcome is Outcome.SCORED

    @property
    def escalates(self) -> bool:
        """The verifier itself broke, so the run stops rather than scoring on."""
        return self.outcome is Outcome.VERIFIER_ERROR


class Scored(_Verdict):
    outcome: Literal[Outcome.SCORED] = Outcome.SCORED
    metrics: Frozen[str, Metric] = Field(min_length=1)


class Failed(_Verdict):
    outcome: Failure
    reason: NonBlank


Verdict = Annotated[Scored | Failed, Field(discriminator="outcome")]
