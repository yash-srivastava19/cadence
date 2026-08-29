from collections.abc import Sequence

from cadence.control.entities import Candidate, Run, Trial
from cadence.control.model import Model
from cadence.control.patcher import apply_patch
from cadence.control.recall import key_for
from cadence.control.restore import Resumption
from cadence.core.dto import (
    Directive,
    RecordedManifest,
    Report,
    RunHistory,
    Spend,
    Suggestion,
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
from cadence.lifecycle.states import RunState
from cadence.observe.channel import Emitter
from cadence.observe.signals import (
    CandidateBuilt,
    ModelCalled,
    ModelRequested,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunResumed,
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
        resumed: Resumption | None = None,
        cap_usd: float | None = None,
    ) -> None:
        self.run_id = run_id
        self.manifest = manifest
        self.method = method
        self.model = model
        self.runner = runner
        self.seeds = tuple(seeds)
        self.budget = budget
        self.resumed = resumed
        self.cap_usd = cap_usd
        self.spend = Spend()

    def run(self) -> Report:
        self.trace = Emitter(run_id=self.run_id)
        run = self._pick_up() if self.resumed else self._begin()
        # Bound here rather than passed inline, because _search appends to it:
        # a run that dies at trial 400 still has 399 results, and the handlers
        # below are the only place left that can report them.
        results = self._known()
        try:
            return self._search(run, results)
        except NoCandidates as error:
            return self._fail(run, str(error), results)
        except ModelError as error:
            return self._fail(run, f"{type(error).__name__}: {error}", results)
        except SetupError as error:
            return self._fail(run, f"{type(error).__name__}: {error}", results)

    def _begin(self) -> Run:
        run = Run(id=self.run_id)
        run.start()
        self.trace.emit(
            RunStarted,
            method=type(self.method).__name__,
            manifest=self.manifest,
            seeds=self.seeds,
            budget={"trials": float(self.budget)},
        )
        return run

    def _pick_up(self) -> Run:
        """Carry on a run that was already under way.

        The status is set rather than transitioned to: the machine describes
        what a run may do next, and a process that died holding one did not
        leave it anywhere the machine has a word for.
        """
        resumed = self.resumed
        assert resumed is not None  # only called when there is one
        run = Run(id=self.run_id, status=RunState.RUNNING)
        run.trials = resumed.trials
        self.trace.emit(
            RunResumed, trials=resumed.trials, results=len(resumed.history.results)
        )
        return run

    def _known(self) -> list[TrialResult]:
        return list(self.resumed.history.results) if self.resumed else []

    def _search(self, run: Run, results: list[TrialResult]) -> Report:
        scored = sum(1 for result in results if result.verdict.is_scored)
        while True:
            history = self._history(results)
            directive = self.method.next_directive(
                history, TrialBudget(spent=run.trials, budget=self.budget)
            )
            if directive is None:
                return self._finish(run, history, scored)
            if self._overspent():
                # Checked before dispatch rather than after: the point of a
                # cap is the call that does not get made.
                return self._finish(
                    run,
                    history,
                    scored,
                    reason=(
                        f"stopped at the ${self.cap_usd:.2f} cap,"
                        f" having spent ${self.spend.usd:.4f}"
                    ),
                )
            reply = self._one(run, directive)
            run.counted()
            if reply is None:
                continue
            results.append(reply)
            if isinstance(reply.verdict, Failed) and reply.verdict.escalates:
                return self._fail(run, reply.verdict.reason, results)
            scored += reply.verdict.is_scored

    def _overspent(self) -> bool:
        """Whether the next call would go past what the manifest allows.

        Nothing to hold to if the provider has no declared price: `usd` is
        None then, and a cap cannot be enforced against a number nobody gave
        us. Saying so beats stopping a run on an imagined total.
        """
        if self.cap_usd is None or self.spend.usd is None:
            return False
        return self.spend.usd >= self.cap_usd

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
        proposal = suggestion.proposal

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
        measured = self.runner.try_(child.code)
        verdict = measured.verdict
        trial.measure(verdict=verdict)
        trace.emit(
            TrialMeasured,
            verdict=verdict,
            wall_ms=measured.wall_ms,
            task_hash=self.runner.task_hash,
            seeds_hash=self.runner.seeds_hash,
        )
        return TrialResult(code=code, verdict=verdict)

    def _propose(self, run: Run, trial: Trial, trace, directive: Directive):
        # An unparseable reply is worth asking again for: it costs a model call,
        # not a trial. Only once the retry budget is gone is the trial lost.
        problem: str | None = None
        while True:
            request = self.model.prepare(
                directive,
                key=key_for(self.run_id, run.trials, trial.attempts),
                # What went wrong last time, so the second ask is a better
                # question than the first rather than the same one. Three
                # identical asks buy three chances at the same mistake.
                problem=problem,
            )
            # Written down before the call is made. A restart that finds this
            # with no answer knows it may already have been paid for.
            trace.emit(
                ModelRequested,
                backend=self.model.backend.name,
                key=request.key,
                prompt_digest=request.digest,
                recipe=request.recipe,
                template=self.model.template,
                template_hash=request.template_hash,
            )
            completion, replayed = None, False
            try:
                completion, replayed = self.model.ask(request)
                # Emitted here, before the reply is read, because this is the
                # moment the answer arrived and the bill was incurred. Emitted
                # after parsing instead, a reply that does not parse leaves the
                # request written down and never answered -- a row that says
                # "we may have paid for this" about a call we know we paid for,
                # every retry, with no crash involved.
                trace.emit(
                    ModelCalled,
                    backend=self.model.backend.name,
                    key=request.key,
                    response=completion.text,
                    model=completion.model,
                    replayed=replayed,
                    **completion.cost,
                )
                proposal = self.model.read(request, completion, directive.code)
                return Suggestion(proposal, completion, replayed, request.key)
            except UnusableReply as error:
                if trial.may_retry:
                    trial.retry()
                    trace.emit(TrialRetried, reason=str(error))
                    problem = str(error)
                    continue
                trial.abandon(reason=str(error))
                trace.emit(TrialAbandoned, reason=str(error))
                return None
            finally:
                # In a finally because the call is billed whether or not we
                # could use what came back. A provider that answers with
                # nothing charged for it, and a run that undercounts its
                # retries reports a price nobody was asked to pay.
                self.spend = self.spend.and_also(
                    completion.tokens_in if completion else 0,
                    completion.tokens_out if completion else 0,
                    replayed,
                    completion.cost_usd if completion else None,
                )

    def _finish(
        self, run: Run, history: RunHistory, scored: int, reason: str | None = None
    ) -> Report:
        best = self.method.best(history)
        run.finish(best=best.verdict.fingerprint if best else None)
        self.trace.emit(
            RunFinished,
            status=run.status,
            trials=run.trials,
            best=run.best,
            reason=reason,
        )
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=scored,
            spend=self.spend,
            best=run.best,
            program=best.code if best else None,
            metrics=best.metrics if best else None,
            reason=reason,
        )

    def _fail(self, run: Run, reason: str, results: list[TrialResult]) -> Report:
        """A run that stopped badly still reports what it earned.

        The trials that scored before the failure were paid for and written
        down; reporting zero of them while the database holds them is two
        accounts of one run. The status and the reason are what say the run
        went wrong -- the results do not have to lie about it as well.
        """
        history = self._history(results)
        best = self.method.best(history)
        run.fail(reason=reason)
        # Assigned rather than transitioned: fail() carries a reason, not a
        # best, and a RunFinished naming a best the entity does not hold
        # would be a second account of the same fact.
        run.best = best.verdict.fingerprint if best else None
        self.trace.emit(
            RunFinished,
            status=run.status,
            trials=run.trials,
            best=run.best,
            reason=reason,
        )
        return Report(
            run_id=self.run_id,
            status=run.status,
            trials=run.trials,
            scored=sum(1 for result in results if result.verdict.is_scored),
            spend=self.spend,
            best=run.best,
            program=best.code if best else None,
            metrics=best.metrics if best else None,
            reason=reason,
        )
