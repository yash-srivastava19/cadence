from collections.abc import Sequence

from cadence.control.entities import Candidate, Run, Trial
from cadence.control.model import Model
from cadence.control.patcher import apply_patch
from cadence.control.recall import key_for
from cadence.core.dto import (
    Directive,
    RecordedManifest,
    Report,
    RunHistory,
    TrialBudget,
    TrialResult,
)
from cadence.core.ports import Method
from cadence.core.verdict import Failed
from cadence.errors import (
    ModelError,
    NoCandidates,
    PatchError,
    SetupError,
    UnusableReply,
)
from cadence.execution.runner import TrialRunner
from cadence.observe.channel import Emitter
from cadence.observe.signals import (
    CandidateBuilt,
    ModelCalled,
    ModelRequested,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunStarted,
    TrialAbandoned,
    TrialMeasured,
    TrialRetried,
    TrialStarted,
)

__all__ = ["Experiment"]


class Experiment:
    def __init__(
        self,
        run_id: str,
        manifest: RecordedManifest,
        method: Method,
        model: Model,
        runner: TrialRunner,
        seeds: Sequence[str],
        budget: int,
    ) -> None:
        self.run_id = run_id
        self.manifest = manifest
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
            manifest=self.manifest,
            seeds=self.seeds,
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
        results: list[TrialResult] = []
        scored = 0
        while True:
            history = self._history(results)
            directive = self.method.next_directive(
                history, TrialBudget(spent=run.trials, budget=self.budget)
            )
            if directive is None:
                return self._finish(run, history, scored)
            reply = self._one(run, directive)
            run.counted()
            if reply is None:
                continue
            results.append(reply)
            if isinstance(reply.verdict, Failed) and reply.verdict.escalates:
                return self._fail(run, reply.verdict.reason)
            scored += reply.verdict.is_scored

    def _history(self, results: list[TrialResult]) -> RunHistory:
        return RunHistory(run_id=self.run_id, seeds=self.seeds, results=tuple(results))

    def _one(self, run: Run, directive: Directive) -> TrialResult | None:
        trial = Trial(
            id=Trial.id_for(self.run_id, run.trials),
            seq=run.trials,
            parent=Candidate(code=directive.code),
        )
        trace = self.trace.about(trial_id=trial.id)
        trace.emit(TrialStarted, seq=trial.seq, parent=directive.parent)

        trial.prompt()
        suggestion = self._propose(run, trial, trace, directive)
        if suggestion is None:
            return None
        proposal, completion, replayed, key = suggestion
        trace.emit(
            ModelCalled,
            backend=self.model.backend.name,
            key=key,
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
        trace.emit(
            CandidateBuilt,
            fingerprint=child.fingerprint,
            code=child.code,
            parent=directive.parent,
        )
        verdict = self.runner.try_(child.code)
        trial.measure(verdict=verdict)
        trace.emit(
            TrialMeasured,
            verdict=verdict,
            task_hash=self.runner.task_hash,
            seeds_hash=self.runner.seeds_hash,
        )
        return TrialResult(code=code, verdict=verdict)

    def _propose(self, run: Run, trial: Trial, trace, directive: Directive):
        # An unparseable reply is worth asking again for: it costs a model call,
        # not a trial. Only once the retry budget is gone is the trial lost.
        while True:
            request = self.model.prepare(
                directive, key=key_for(self.run_id, run.trials, trial.attempts)
            )
            # Written down before the call is made. A restart that finds this
            # with no answer knows it may already have been paid for.
            trace.emit(
                ModelRequested,
                backend=self.model.backend.name,
                key=request.key,
                prompt_digest=request.digest,
                recipe=request.recipe,
            )
            try:
                return self.model.send(request, directive.code)
            except UnusableReply as error:
                if trial.may_retry:
                    trial.retry()
                    trace.emit(TrialRetried, reason=str(error))
                    continue
                trial.abandon(reason=str(error))
                trace.emit(TrialAbandoned, reason=str(error))
                return None

    def _finish(self, run: Run, history: RunHistory, scored: int) -> Report:
        best = self.method.best(history)
        run.finish(best=best.verdict.fingerprint if best else None)
        self.trace.emit(
            RunFinished, status=run.status, trials=run.trials, best=run.best
        )
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=scored,
            best=run.best,
            program=best.code if best else None,
            metrics=best.metrics if best else None,
        )

    def _fail(self, run: Run, reason: str) -> Report:
        run.fail(reason=reason)
        self.trace.emit(
            RunFinished,
            status=run.status,
            trials=run.trials,
            best=None,
            reason=reason,
        )
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=0,
            reason=reason,
        )
