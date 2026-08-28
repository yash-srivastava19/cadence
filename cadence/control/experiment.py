from collections.abc import Sequence

from cadence.control.entities import Candidate, Run, Trial, trial_id
from cadence.control.model import Model
from cadence.control.patcher import apply_patch
from cadence.control.recall import key_for
from cadence.core.dto import Attempt, Directive, History, Ledger, Report
from cadence.core.ports import Method
from cadence.errors import ModelError, NoCandidates, PatchError, SetupError
from cadence.execution.runner import TrialRunner
from cadence.observe.channel import Emitter
from cadence.observe.signals import (
    ModelCalled,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunStarted,
    TrialAbandoned,
    TrialMeasured,
    TrialStarted,
)

__all__ = ["Experiment"]


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
        except SetupError as error:
            return self._fail(run, f"{type(error).__name__}: {error}")

    def _search(self, run: Run) -> Report:
        attempts: list[Attempt] = []
        scored = 0
        while True:
            history = self._history(attempts)
            directive = self.method.next_directive(
                history, Ledger(spent=run.trials, budget=self.budget)
            )
            if directive is None:
                return self._finish(run, history, scored)
            reply = self._one(run, directive)
            run.counted()
            if reply is None:
                continue
            attempts.append(reply)
            if reply.verdict.escalates:
                return self._fail(run, reply.verdict.reason)
            scored += reply.verdict.is_scored

    def _history(self, attempts: list[Attempt]) -> History:
        return History(run_id=self.run_id, seeds=self.seeds, attempts=tuple(attempts))

    def _one(self, run: Run, directive: Directive) -> Attempt | None:
        trial = Trial(
            id=trial_id(self.run_id, run.trials, 0),
            parent=Candidate(code=directive.code),
        )
        trace = self.trace.about(trial_id=trial.id)
        trace.emit(TrialStarted, parent=directive.parent)

        trial.prompt()
        suggestion = self._propose(run, trial, trace, directive)
        if suggestion is None:
            return None
        proposal, completion, replayed = suggestion
        trace.emit(
            ModelCalled,
            backend=self.model.backend.name,
            replayed=replayed,
            **completion.cost,
        )

        trial.generate(proposal=proposal)
        trace.emit(ProposalReceived, files_changed=proposal.files_changed)

        try:
            code = apply_patch(directive.code, proposal.patch)
        except PatchError as error:
            trial.reject(reason=str(error))
            trace.emit(PatchRejected, reason=str(error))
            return None

        child = Candidate(code=code, parent=directive.parent)
        trial.apply_patch(candidate=child)
        verdict = self.runner.try_(child.code)
        trial.measure(verdict=verdict)
        trace.emit(TrialMeasured, verdict=verdict)
        return Attempt(code=code, verdict=verdict)

    def _propose(self, run: Run, trial: Trial, trace, directive: Directive):
        # An unparseable reply is worth asking again for: it costs a model call,
        # not a trial. Only once the retry budget is gone is the trial lost.
        while True:
            try:
                return self.model.propose(
                    directive,
                    key=key_for(self.run_id, run.trials, trial.attempts),
                )
            except PatchError as error:
                if trial.may_retry:
                    trial.retry()
                    trace.emit(PatchRejected, reason=str(error))
                    continue
                trial.abandon(reason=str(error))
                trace.emit(TrialAbandoned, reason=str(error))
                return None

    def _finish(self, run: Run, history: History, scored: int) -> Report:
        best = self.method.best(history)
        run.finish(best=best.verdict.fingerprint if best else None)
        self.trace.emit(RunFinished, trials=run.trials, best=run.best)
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=scored,
            best=run.best,
            program=best.code if best else None,
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
