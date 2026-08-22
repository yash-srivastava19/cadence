from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from cadence.entities import Candidate, Run, Trial, trial_id
from cadence.exceptions import ModelError, NoCandidates, PatchError
from cadence.interfaces import Attempt, Method, Metrics
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
        run.start()
        RunStarted(
            run_id=self.run_id,
            method=type(self.method).__name__,
            budget={"trials": float(self.budget)},
        ).emit()

        scored = 0
        try:
            search = self.method.search(self.seeds, self.budget)
            reply: Attempt | None = None
            while True:
                try:
                    directive = search.send(reply)
                except StopIteration:
                    break
                trial = Trial(
                    id=trial_id(self.run_id, run.trials, 0),
                    parent=Candidate(code=directive.code),
                )
                run.counted()
                reply = self._one(trial, directive)
                if reply is not None and reply.verdict.is_scored:
                    scored += 1
                if reply is not None and reply.verdict.escalates:
                    return self._fail(run, reply.verdict.reason)
        except NoCandidates as error:
            return self._fail(run, str(error))
        except ModelError as error:
            return self._fail(run, f"{type(error).__name__}: {error}")

        return self._finish(run, scored)

    def _one(self, trial: Trial, directive) -> Attempt | None:
        TrialStarted(
            run_id=self.run_id, trial_id=trial.id, parent=directive.parent
        ).emit()
        trial.prompt()

        try:
            proposal, completion = self.model.propose(directive)
        except PatchError as error:
            trial.abandon(reason=str(error))
            TrialAbandoned(
                run_id=self.run_id, trial_id=trial.id, reason=str(error)
            ).emit()
            return None
        ModelCalled(
            run_id=self.run_id,
            trial_id=trial.id,
            backend=self.model.backend.name,
            tokens_in=completion.tokens_in,
            tokens_out=completion.tokens_out,
            latency_ms=completion.latency_ms,
        ).emit()
        trial.generate(proposal=proposal)
        ProposalReceived(
            run_id=self.run_id, trial_id=trial.id, files_changed=len(proposal.patch)
        ).emit()

        try:
            code = apply_patch(directive.code, proposal.patch)
        except PatchError as error:
            trial.reject(reason=str(error))
            PatchRejected(
                run_id=self.run_id, trial_id=trial.id, reason=str(error)
            ).emit()
            return None

        child = Candidate(code=code, parent=directive.parent)
        trial.apply_patch(candidate=child)
        verdict = self.runner.try_(child)
        trial.measure(verdict=verdict)
        TrialMeasured(run_id=self.run_id, trial_id=trial.id, verdict=verdict).emit()
        return Attempt(code=code, verdict=verdict)

    def _finish(self, run: Run, scored: int) -> Report:
        best = self.method.best() if hasattr(self.method, "best") else None
        fingerprint = best.candidate.fingerprint if best and best.measured else None
        metrics: Metrics | None = dict(best.metrics) if best and best.measured else None
        run.finish(best=fingerprint)
        RunFinished(run_id=self.run_id, trials=run.trials, best=fingerprint).emit()
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=scored,
            best=fingerprint,
            metrics=metrics,
        )

    def _fail(self, run: Run, reason: str) -> Report:
        run.fail(reason=reason)
        TrialAbandoned(run_id=self.run_id, trial_id=self.run_id, reason=reason).emit()
        RunFinished(run_id=self.run_id, trials=run.trials, best=None).emit()
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=0,
            reason=reason,
        )
