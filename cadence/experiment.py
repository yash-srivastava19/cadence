from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from cadence.entities import Candidate, Run, Trial, trial_id
from cadence.exceptions import ModelError, NoCandidates, PatchError
from cadence.events import Emitter
from cadence.interfaces import Attempt, Directive, Method
from cadence.model import Model
from cadence.patcher import apply_patch
from cadence.runner import TrialRunner
from cadence.signals import (
    ModelCalled,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunStarted,
    TrialAbandoned,
    TrialMeasured,
    TrialStarted,
)
from cadence.states import RunState

__all__ = ["Report", "Experiment"]


class Report(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    run_id: str
    status: RunState
    trials: int = Field(ge=0)
    scored: int = Field(ge=0)
    best: str | None = None
    metrics: Mapping[str, float] | None = None
    reason: str | None = None


class Experiment:
    def __init__(
        self,
        run_id: str,
        method: Method,
        model: Model,
        runner: TrialRunner,
        seeds: Sequence[str],
        budget: int,
    ) -> None:
        self.run_id = run_id
        self.method = method
        self.model = model
        self.runner = runner
        self.seeds = tuple(seeds)
        self.budget = budget

    def run(self) -> Report:
        run = Run(id=self.run_id)
        self.trace = Emitter(run_id=self.run_id)
        run.start()
        self.trace.emit(
            RunStarted,
            method=type(self.method).__name__,
            budget={"trials": float(self.budget)},
        )
        try:
            return self._search(run)
        except NoCandidates as error:
            return self._fail(run, str(error))
        except ModelError as error:
            return self._fail(run, f"{type(error).__name__}: {error}")

    def _search(self, run: Run) -> Report:
        scored = 0
        search = self.method.search(self.seeds, self.budget)
        reply: Attempt | None = None
        while True:
            try:
                directive = search.send(reply)
            except StopIteration:
                return self._finish(run, scored)
            run.counted()
            reply = self._one(run, directive)
            if reply is None:
                continue
            if reply.verdict.escalates:
                return self._fail(run, reply.verdict.reason)
            scored += reply.verdict.is_scored

    def _one(self, run: Run, directive: Directive) -> Attempt | None:
        trial = Trial(
            id=trial_id(self.run_id, run.trials, 0),
            parent=Candidate(code=directive.code),
        )
        trace = self.trace.about(trial_id=trial.id)
        trace.emit(TrialStarted, parent=directive.parent)

        trial.prompt()
        try:
            proposal, completion = self.model.propose(directive)
        except PatchError as error:
            trial.abandon(reason=str(error))
            trace.emit(TrialAbandoned, reason=str(error))
            return None
        trace.emit(ModelCalled, backend=self.model.backend.name, **completion.cost)

        trial.generate(proposal=proposal)
        trace.emit(ProposalReceived, files_changed=len(proposal.patch))

        try:
            code = apply_patch(directive.code, proposal.patch)
        except PatchError as error:
            trial.reject(reason=str(error))
            trace.emit(PatchRejected, reason=str(error))
            return None

        child = Candidate(code=code, parent=directive.parent)
        trial.apply_patch(candidate=child)
        verdict = self.runner.try_(child)
        trial.measure(verdict=verdict)
        trace.emit(TrialMeasured, verdict=verdict)
        return Attempt(code=code, verdict=verdict)

    def _finish(self, run: Run, scored: int) -> Report:
        best = self.method.best()
        run.finish(best=best.verdict.fingerprint if best else None)
        self.trace.emit(RunFinished, trials=run.trials, best=run.best)
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=scored,
            best=run.best,
            metrics=dict(best.verdict.metrics) if best else None,
        )

    def _fail(self, run: Run, reason: str) -> Report:
        run.fail(reason=reason)
        self.trace.emit(RunFinished, trials=run.trials, best=None)
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=0,
            reason=reason,
        )
