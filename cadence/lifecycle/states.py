from enum import StrEnum

__all__ = [
    "CandidateState",
    "RunState",
    "SandboxRunState",
    "Severity",
    "TrialState",
    "severity_of",
]


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TrialState(StrEnum):
    STARTED = "started"
    PROMPTED = "prompted"
    GENERATED = "generated"
    MATERIALIZED = "materialized"
    MEASURED = "measured"
    UNUSABLE = "unusable"
    ABANDONED = "abandoned"


class CandidateState(StrEnum):
    ALIVE = "alive"
    RETIRED = "retired"
    QUARANTINED = "quarantined"


class SandboxRunState(StrEnum):
    RUNNING = "running"
    REAPED = "reaped"
    KILLED = "killed"
    ORPHANED = "orphaned"


class Severity(StrEnum):
    """How much attention a state is owed.

    Here rather than in whatever is drawing, so a state added to the enums
    above cannot be silently rendered as ordinary by a surface that has not
    heard of it.
    """

    NOMINAL = "nominal"
    CAUTION = "caution"
    LIMIT = "limit"


_SERIOUS = {
    RunState.FAILED,
    RunState.CANCELLED,
    TrialState.UNUSABLE,
    "crashed",
    "timed_out",
    "rejected",
}
_WATCH = {
    RunState.RUNNING,
    RunState.PENDING,
    RunState.PAUSED,
    TrialState.STARTED,
    TrialState.PROMPTED,
    TrialState.GENERATED,
    TrialState.MATERIALIZED,
    TrialState.ABANDONED,
    "stalled",
    "retried",
}


def severity_of(state: str) -> Severity:
    if state in _SERIOUS:
        return Severity.LIMIT
    if state in _WATCH:
        return Severity.CAUTION
    return Severity.NOMINAL
