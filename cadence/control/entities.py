"""The three things a run is made of, and the moves each one allows.

A machine per entity, declared beside it. Every verb below is a real method:
what it does to the entity is next to what makes it legal, and both are next
to the states they move between.
"""

from statemachine import State, StateMachine

from cadence.core.dto import Proposal
from cadence.core.identity import fingerprint
from cadence.core.verdict import Verdict
from cadence.lifecycle.entity import Entity
from cadence.lifecycle.states import CandidateState, RunState, TrialState

__all__ = [
    "Candidate",
    "CandidateStateMachine",
    "Run",
    "RunStateMachine",
    "Trial",
    "TrialStateMachine",
]


class CandidateStateMachine(StateMachine):
    alive = State(value=CandidateState.ALIVE, initial=True)
    retired = State(value=CandidateState.RETIRED, final=True)
    quarantined = State(value=CandidateState.QUARANTINED, final=True)

    retire = alive.to(retired)
    quarantine = alive.to(quarantined, cond="exceeded_crash_limit")


class Candidate(Entity, machine=CandidateStateMachine):
    """A program the search is holding on to."""

    crash_limit = 3

    def __init__(
        self,
        code: str,
        parent: str | None = None,
        status: CandidateState | None = None,
    ) -> None:
        self.code = code
        self.parent = parent
        self.crashes = 0
        self.status = status or CandidateState.ALIVE
        self.bind()

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.code)

    @property
    def is_alive(self) -> bool:
        return self.status == CandidateState.ALIVE

    @property
    def may_quarantine(self) -> bool:
        return self._permits("quarantine")

    def crashed(self) -> None:
        self.crashes += 1

    def exceeded_crash_limit(self) -> bool:
        """Guards quarantine. A candidate that keeps crashing is poison."""
        return self.crashes >= self.crash_limit

    def retire(self) -> None:
        """Evicted from the population. It was simply beaten."""
        self._fire("retire")

    def quarantine(self) -> None:
        """Never tried again. Refused unless it has crashed often enough."""
        self._fire("quarantine")


class TrialStateMachine(StateMachine):
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


class Trial(Entity, machine=TrialStateMachine):
    """One pass down the pipeline: ask, parse, apply, run, score.

    The Trial tracks how far it got. The Verdict says what the result was.
    They deliberately do not mirror each other -- two machines describing one
    event would be a second source of truth. `unusable` is a trial state and
    not an outcome because nothing ran, so there is no result to describe.
    """

    max_attempts = 3

    def __init__(
        self,
        id: str,
        seq: int,
        parent: Candidate,
        status: TrialState | None = None,
    ) -> None:
        self.id = id
        self.seq = seq
        self.parent = parent
        self.attempts = 0
        self.proposal: Proposal | None = None
        self.candidate: Candidate | None = None
        self.verdict: Verdict | None = None
        self.reason: str | None = None
        self.status = status or TrialState.STARTED
        self.bind()

    @staticmethod
    def id_for(run: str, seq: int) -> str:
        """Derived, never generated.

        uuid4 would make every construction unique, so a retry after a crash
        could not be recognised as the same trial. seq is the trial's position
        in its run, and it is the same number the trials table is unique on --
        two ways of counting the same thing would eventually disagree.
        """
        return f"{run}/{seq}"

    @property
    def may_prompt(self) -> bool:
        return self._permits("prompt")

    @property
    def may_retry(self) -> bool:
        return self._permits("retry")

    @property
    def may_measure(self) -> bool:
        return self._permits("measure")

    def under_retry_budget(self) -> bool:
        """Guards retry."""
        return self.attempts < self.max_attempts

    def prompt(self) -> None:
        """The prompt is built and about to be sent."""
        self._fire("prompt")

    def retry(self) -> None:
        """The reply was unusable. Ask again, at the cost of a call, not a trial."""
        self._fire("retry")
        self.attempts += 1

    def generate(self, proposal: Proposal) -> None:
        self._fire("generate", proposal=proposal)
        self.proposal = proposal

    def apply_patch(self, candidate: Candidate) -> None:
        self._fire("apply_patch", candidate=candidate)
        self.candidate = candidate

    def reject(self, reason: str) -> None:
        """The diff would not apply, even after recount."""
        self._fire("reject", reason=reason)
        self.reason = reason

    def measure(self, verdict: Verdict) -> None:
        self._fire("measure", verdict=verdict)
        self.verdict = verdict

    def abandon(self, reason: str) -> None:
        """Retries exhausted, or a terminal model error."""
        self._fire("abandon", reason=reason)
        self.reason = reason


class RunStateMachine(StateMachine):
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


class Run(Entity, machine=RunStateMachine):
    """One invocation of `cadence run`, from pending to a final state."""

    def __init__(self, id: str, status: RunState | None = None) -> None:
        self.id = id
        self.trials = 0
        self.best: str | None = None
        self.reason: str | None = None
        self.status = status or RunState.PENDING
        self.bind()

    @property
    def may_start(self) -> bool:
        return self._permits("start")

    @property
    def may_cancel(self) -> bool:
        return self._permits("cancel")

    def has_a_reason(self, reason: str | None = None) -> bool:
        """Guards fail. A failed run that cannot say why is not a report."""
        return bool(reason)

    def counted(self) -> None:
        self.trials += 1

    def start(self) -> None:
        self._fire("start")

    def pause(self) -> None:
        self._fire("pause")

    def resume(self) -> None:
        self._fire("resume")

    def cancel(self) -> None:
        self._fire("cancel")

    def finish(self, best: str | None = None) -> None:
        self._fire("finish", best=best)
        self.best = best

    def fail(self, reason: str) -> None:
        self._fire("fail", reason=reason)
        self.reason = reason
