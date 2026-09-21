from collections.abc import Sequence

from cadence.control.entities import Candidate, Run, Trial
from cadence.control.model import Model
from cadence.control.patcher import apply_patch
from cadence.control.recall import key_for
from cadence.control.restore import Resumption
from cadence.core.dto import (
    Directive,
    Proposal,
    RecordedManifest,
    Report,
    RunHistory,
    Spend,
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
from cadence.observe.channel import Emitter, Fact
from cadence.observe.signals import (
    CandidateBuilt,
    ModelCalled,
    ModelRequested,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunResumed,
    RunStarted,
    SeedMeasured,
    TrialAbandoned,
    TrialMeasured,
    TrialRetried,
    TrialStarted,
    cadence,
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
        owner: str | None = None,
        experiment: str | None = None,
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
        self.owner = owner
        self.experiment = experiment
        #: What the run has spent, counted from its own facts by `Spent`.
        self.spent = Spent(self.run_id)
        #: What the programs the run started from scored. None until measured,
        #: and on a resumed run it stays None -- the first run took it.
        self.baseline: TrialResult | None = None

    def run(self) -> Report:
        self.trace = Emitter(run_id=self.run_id)
        counting = cadence.subscribe(self.spent.on)
        try:
            return self._go()
        finally:
            counting()

    def _go(self) -> Report:
        run = self._pick_up() if self.resumed else self._begin()
        # Bound here rather than passed inline, because _search appends to it:
        # a run that dies at trial 400 still has 399 results, and the handlers
        # below are the only place left that can report them.
        results = self._known()
        try:
            if not self.resumed:
                self._measure_the_seeds()
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
            owner=self.owner,
            experiment=self.experiment,
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

    def _measure_the_seeds(self) -> None:
        """Score the programs the run started from, before improving on them.

        Without this a run has no measurement of its own starting point.
        `best` was the best of the children, so every child being worse than
        the seed still produced a winner -- and `cadence apply` would write
        that winner over a better program.

        Not a trial: no model call, nothing proposed, and nothing counted
        against the budget. Only on a fresh run, because a resumed one has
        these results already.

        A seed that will not score is left out rather than fatal. The run can
        still improve on a program whose baseline could not be taken; it just
        cannot claim it did.

        Deliberately NOT appended to history.results. The prompt renders what
        the run has scored so far, so a seed in there would change trial 0's
        prompt from "Nobody has scored yet" to a real number -- and recall.py
        replays a paid-for model call only when the prompt digest matches, so
        every run recorded before this change would refuse to resume. Telling
        the model its baseline is worth doing and is a separate decision with
        that cost attached to it.
        """
        for code in self.seeds:
            measured = self.runner.try_(code)
            self.trace.emit(
                SeedMeasured,
                fingerprint=Candidate(code=code).fingerprint,
                verdict=measured.verdict,
                wall_ms=measured.wall_ms,
                task_hash=self.runner.task_hash,
                seeds_hash=self.runner.seeds_hash,
            )
            if measured.verdict.is_scored:
                self.baseline = TrialResult(code=code, verdict=measured.verdict)

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
                        f" having spent ${self.spent.total.usd:.4f}"
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
        if self.cap_usd is None or self.spent.total.usd is None:
            return False
        return self.spent.total.usd >= self.cap_usd

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
        proposal = self._propose(run, trial, trace, directive)
        if proposal is None:
            return None

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

    def _propose(
        self, run: Run, trial: Trial, trace, directive: Directive
    ) -> Proposal | None:
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
                return self.model.read(request, completion, directive.code)
            except UnusableReply as error:
                if trial.may_retry:
                    trial.retry()
                    trace.emit(TrialRetried, reason=str(error))
                    problem = str(error)
                    continue
                trial.abandon(reason=str(error))
                trace.emit(TrialAbandoned, reason=str(error))
                return None

    def _winner(self, history: RunHistory) -> TrialResult | None:
        """The best program the run has, which may be the one it started from.

        The search only ever ranks what it produced, so a run whose every
        child scored worse than the seed still named a child the winner. That
        is not a weak result, it is a wrong one: `cadence apply` would write
        it over a better program and call it an improvement.

        Ranked by the method, on a history built here and used for nothing
        else. The search decides what "better" means; this only makes sure
        the program the run started from is one of the things it decides
        between. Built at report time so the prompt never sees it -- a seed
        in history.results would change what trial 0 asks, and recall.py
        replays a paid-for call only when the prompt digest still matches.
        """
        if self.baseline is None:
            return self.method.best(history)
        return self.method.best(
            RunHistory(
                run_id=history.run_id,
                seeds=history.seeds,
                results=(*history.results, self.baseline),
            )
        )

    def _finish(
        self, run: Run, history: RunHistory, scored: int, reason: str | None = None
    ) -> Report:
        best = self._winner(history)
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
            spend=self.spent.total,
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
        best = self._winner(history)
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
            spend=self.spent.total,
            best=run.best,
            program=best.code if best else None,
            metrics=best.metrics if best else None,
            reason=reason,
        )


class Spent:
    """What a run has spent so far, counted from its own facts.

    A subscriber to the same channel the journal records, not a bookkeeping
    line inside the loop: the loop should not know what a token is, and the
    facts already carry the bill. Two facts count two different things.

        ModelRequested  the ask, written before the call -- so a request the
                        provider never answered is still an ask, which is the
                        whole point of it being written first.
        ModelCalled     the answer: tokens always, and the price only when the
                        answer was bought this run, never when it was replayed.

    Subscribers are best effort by the channel's rule, which is acceptable
    here: a counting mistake can only under-report, and the same facts are on
    the tape for anyone to recount. The facts are delivered synchronously, so
    the total is current when the loop asks it before the next dispatch.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.total = Spend()

    def on(self, fact: Fact) -> None:
        if getattr(fact, "run_id", None) != self.run_id:
            return  # not this run's fact; one counter per run
        if isinstance(fact, ModelRequested):
            self.total = self.total.called()
        elif isinstance(fact, ModelCalled):
            self.total = self.total.answered(
                fact.tokens_in, fact.tokens_out, fact.replayed, fact.cost_usd
            )
