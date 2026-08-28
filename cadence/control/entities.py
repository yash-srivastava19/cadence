from statemachine import State, StateMachine

from cadence.core.identity import fingerprint
from cadence.lifecycle.stateful import Stateful
from cadence.lifecycle.states import CandidateState, RunState, TrialState

__all__ = [
    "Candidate",
    "CandidateMachine",
    "Run",
    "RunMachine",
    "Trial",
    "TrialMachine",
    "trial_id",
]


def trial_id(run: str, generation: int, index: int) -> str:
    return f"{run}/{generation}/{index}"


class CandidateMachine(StateMachine):
    alive = State(value=CandidateState.ALIVE, initial=True)
    retired = State(value=CandidateState.RETIRED, final=True)
    quarantined = State(value=CandidateState.QUARANTINED, final=True)

    retire = alive.to(retired)
    quarantine = alive.to(quarantined, cond="crashes_too_often")


class Candidate(Stateful, machine=CandidateMachine):
    crash_limit = 3

    def __init__(self, code: str, parent: str | None = None, status=None) -> None:
        self.code = code
        self.parent = parent
        self.crashes = 0
        self.status = status
        self.bind()

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.code)

    def crashed(self) -> None:
        self.crashes += 1

    def crashes_too_often(self) -> bool:
        return self.crashes >= self.crash_limit


class TrialMachine(StateMachine):
    started = State(value=TrialState.STARTED, initial=True)
    prompted = State(value=TrialState.PROMPTED)
    generated = State(value=TrialState.GENERATED)
    materialized = State(value=TrialState.MATERIALIZED)
    measured = State(value=TrialState.MEASURED, final=True)
    unusable = State(value=TrialState.UNUSABLE, final=True)
    abandoned = State(value=TrialState.ABANDONED, final=True)

    prompt = started.to(prompted)
    retry = prompted.to.itself(cond="under_retry_budget")
    generate = prompted.to(generated)
    apply_patch = generated.to(materialized)
    reject = generated.to(unusable)
    measure = materialized.to(measured)
    abandon = (
        started.to(abandoned)
        | prompted.to(abandoned)
        | generated.to(abandoned)
        | materialized.to(abandoned)
    )


class Trial(Stateful, machine=TrialMachine):
    max_attempts = 3

    def __init__(self, id: str, parent: Candidate, status=None) -> None:
        self.id = id
        self.parent = parent
        self.attempts = 0
        self.proposal = None
        self.candidate = None
        self.verdict = None
        self.reason = None
        self.status = status
        self.bind()

    def under_retry_budget(self) -> bool:
        return self.attempts < self.max_attempts

    def on_retry(self) -> None:
        self.attempts += 1

    def on_generate(self, proposal) -> None:
        self.proposal = proposal

    def on_apply_patch(self, candidate: Candidate) -> None:
        self.candidate = candidate

    def on_reject(self, reason: str) -> None:
        self.reason = reason

    def on_measure(self, verdict) -> None:
        self.verdict = verdict

    def on_abandon(self, reason: str) -> None:
        self.reason = reason


class RunMachine(StateMachine):
    pending = State(value=RunState.PENDING, initial=True)
    running = State(value=RunState.RUNNING)
    paused = State(value=RunState.PAUSED)
    finished = State(value=RunState.FINISHED, final=True)
    cancelled = State(value=RunState.CANCELLED, final=True)
    failed = State(value=RunState.FAILED, final=True)

    start = pending.to(running)
    pause = running.to(paused)
    resume = paused.to(running)
    finish = running.to(finished)
    fail = running.to(failed, cond="has_a_reason")
    cancel = pending.to(cancelled) | running.to(cancelled) | paused.to(cancelled)


class Run(Stateful, machine=RunMachine):
    def __init__(self, id: str, status=None) -> None:
        self.id = id
        self.trials = 0
        self.best = None
        self.reason = None
        self.status = status
        self.bind()

    def has_a_reason(self, reason: str | None = None) -> bool:
        return bool(reason)

    def on_fail(self, reason: str) -> None:
        self.reason = reason

    def on_finish(self, best: str | None = None) -> None:
        self.best = best

    def counted(self) -> None:
        self.trials += 1
