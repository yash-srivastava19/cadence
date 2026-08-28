from enum import StrEnum

__all__ = ["CandidateState", "RunState", "SandboxRunState", "TrialState"]


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
