from cadence.control.backends import Scripted
from cadence.control.entities import Trial
from cadence.control.experiment import Experiment
from cadence.control.methods.evolution import Evolution
from cadence.control.model import Model
from cadence.control.objectives.ranking import WeightedSum
from cadence.core.dto import Report
from cadence.errors import EmptyReply, TerminalModelError
from cadence.execution.runner import TrialRunner
from cadence.execution.sandboxes.subprocess import Subprocess
from cadence.lifecycle.states import RunState
from cadence.observe.signals import cadence
from tests.factories import a_manifest

BASELINE = "print('value: 0')"


def rewritten(program):
    return f"Here is the new program.\n```python\n{program}\n```"


IMPROVES = rewritten("print('value: 9')")
SILENT = rewritten("print('nothing to report')")
CRASHES = rewritten("raise ValueError('the evolved code is broken')")
NONSENSE = "I would change the loop, but here is prose instead."
# One first ask plus every retry the trial is allowed.
GIVES_UP = [NONSENSE] * (Trial.max_attempts + 1)


def an_experiment(*responses, budget=1, metrics=None):
    return Experiment(
        run_id="h1",
        manifest=a_manifest(),
        method=Evolution(objective=WeightedSum(value=1.0)),
        model=Model(backend=Scripted(*responses)),
        runner=TrialRunner(
            program="prog.py",
            command=("python", "prog.py"),
            metrics=metrics or {"value": "maximize"},
            sandbox=Subprocess(),
            seeds=(0,),
        ),
        seeds=[BASELINE],
        budget=budget,
    )


class TestAFullOfflineRun:
    def test_it_finishes(self):
        assert an_experiment(IMPROVES).run().status == RunState.FINISHED

    def test_it_scores_the_candidate_it_produced(self):
        assert an_experiment(IMPROVES).run().scored == 1

    def test_it_names_a_best(self):
        assert an_experiment(IMPROVES).run().best is not None

    def test_the_improvement_is_real(self):
        assert an_experiment(IMPROVES).run().metrics["value"] == 9.0

    def test_it_returns_the_program_it_ended_with(self):
        assert "value: 9" in an_experiment(IMPROVES).run().program

    def test_the_report_survives_json(self):
        report = an_experiment(IMPROVES).run()
        assert Report.model_validate_json(report.model_dump_json()) == report


class TestTheRunIsTraceable:
    def test_the_tape_reads_start_to_finish(self):
        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        assert [type(fact).__name__ for fact in tape] == [
            "RunStarted",
            "TrialStarted",
            "ModelRequested",
            "ModelCalled",
            "ProposalReceived",
            "CandidateBuilt",
            "TrialMeasured",
            "RunFinished",
        ]

    def test_every_event_names_the_run(self):
        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        assert {fact.run_id for fact in tape} == {"h1"}

    def test_the_model_call_reports_what_it_cost(self):
        from cadence.observe.signals import ModelCalled

        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        called = tape.of(ModelCalled)[0]
        assert called.tokens_in > 0
        assert called.tokens_out > 0

    def test_the_measured_event_carries_the_verdict(self):
        from cadence.observe.signals import TrialMeasured

        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        assert tape.of(TrialMeasured)[0].verdict.is_scored

    def test_an_abandoned_trial_is_visible_on_the_tape(self):
        from cadence.observe.signals import TrialAbandoned

        with cadence.recording() as tape:
            an_experiment(*GIVES_UP).run()
        assert "```python block" in tape.of(TrialAbandoned)[0].reason


class TestFailingWell:
    def test_an_unparseable_answer_abandons_the_trial_not_the_run(self):
        report = an_experiment(*GIVES_UP).run()
        assert report.status == RunState.FINISHED
        assert report.scored == 0

    def test_an_unparseable_answer_is_asked_again_before_being_given_up_on(self):
        experiment = an_experiment(NONSENSE, IMPROVES)
        report = experiment.run()
        assert report.scored == 1
        assert len(experiment.model.backend.prompts) == 2

    def test_a_retry_does_not_cost_a_trial(self):
        report = an_experiment(NONSENSE, IMPROVES).run()
        assert report.trials == 1

    def test_retries_are_bounded_by_the_trial_budget(self):
        experiment = an_experiment(*GIVES_UP)
        experiment.run()
        assert len(experiment.model.backend.prompts) == Trial.max_attempts + 1

    def test_a_program_that_crashes_is_measured_not_fatal(self):
        report = an_experiment(CRASHES).run()
        assert report.status == RunState.FINISHED
        assert report.scored == 0

    def test_a_program_that_reports_nothing_is_measured_not_fatal(self):
        report = an_experiment(SILENT).run()
        assert report.status == RunState.FINISHED
        assert report.scored == 0

    def test_running_out_of_backend_ends_the_run(self):
        report = an_experiment(IMPROVES, budget=2).run()
        assert report.status == RunState.FAILED

    def test_a_terminal_model_error_is_not_retried_into_the_ground(self):
        experiment = an_experiment(TerminalModelError("401"))
        assert experiment.run().status == RunState.FAILED
        assert len(experiment.model.backend.prompts) == 1

    def test_a_reply_with_nothing_in_it_costs_a_trial_not_the_run(self):
        """A content filter is about one prompt. Ending a 500-trial run on it
        would be worse than the empty completion this replaced."""
        experiment = an_experiment(EmptyReply("no choices"), IMPROVES)
        report = experiment.run()
        assert report.status == RunState.FINISHED
        assert report.scored == 1


class TestAFailedRunKeepsWhatItEarned:
    """A run that stops badly has still spent money and still learned things.

    Reporting zero of them while the database holds the verdicts is two
    accounts of one run, and the one the user reads is the wrong one.
    """

    def _ran_out(self, budget=2):
        # One answer, two trials: the second ask finds the backend empty.
        return an_experiment(IMPROVES, budget=budget).run()

    def test_the_run_is_reported_as_failed(self):
        assert self._ran_out().status == RunState.FAILED

    def test_it_counts_the_trial_that_scored(self):
        assert self._ran_out().scored == 1

    def test_it_names_the_best_it_found(self):
        assert self._ran_out().best is not None

    def test_it_returns_the_program_that_scored(self):
        assert "value: 9" in self._ran_out().program

    def test_it_carries_the_metrics(self):
        assert self._ran_out().metrics["value"] == 9.0

    def test_it_still_says_why_it_stopped(self):
        assert "scripted backend ran out" in self._ran_out().reason

    def test_the_tape_names_the_same_best_the_report_does(self):
        """Otherwise the row in `runs` and the sentence on the terminal
        disagree about the same run."""
        from cadence.observe.signals import RunFinished

        with cadence.recording() as tape:
            report = an_experiment(IMPROVES, budget=2).run()
        assert tape.of(RunFinished)[0].best == report.best

    def test_a_run_that_earned_nothing_still_names_no_best(self):
        assert an_experiment(TerminalModelError("401")).run().best is None


class TestABrokenProjectStopsTheRun:
    TWO_MARKERS = "# CADENCE:BEGIN\nx = 1\n# CADENCE:BEGIN\ny = 2\n# CADENCE:END\n"

    def _marked(self, program):
        experiment = an_experiment(IMPROVES)
        experiment.seeds = (program,)
        experiment.model.template = "region"
        return experiment

    def test_a_malformed_marked_region_fails_the_run(self):
        report = self._marked(self.TWO_MARKERS).run()
        assert report.status == RunState.FAILED

    def test_it_says_which_marker_is_wrong(self):
        report = self._marked(self.TWO_MARKERS).run()
        assert "CADENCE:BEGIN" in report.reason

    def test_it_is_not_retried_because_retrying_cannot_help(self):
        experiment = self._marked(self.TWO_MARKERS)
        experiment.run()
        assert len(experiment.model.backend.prompts) == 1


class TestEveryTransitionIsOnTheTape:
    """The entities do not emit; Experiment fires the transition and reports
    the fact, in one function. That keeps a run_id out of Candidate, and it
    makes this test the thing that stops the two halves drifting apart."""

    def test_a_scored_trial_reports_every_step_it_took(self):
        from cadence.observe.signals import (
            CandidateBuilt,
            ModelCalled,
            ModelRequested,
            ProposalReceived,
            RunFinished,
            RunStarted,
            TrialMeasured,
            TrialStarted,
        )

        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        reported = [type(fact) for fact in tape]
        assert reported == [
            RunStarted,
            TrialStarted,
            ModelRequested,
            ModelCalled,
            ProposalReceived,
            CandidateBuilt,
            TrialMeasured,
            RunFinished,
        ]

    def test_a_reply_that_does_not_parse_is_still_reported_as_a_call(self):
        """The write-ahead row is closed by ModelCalled. Emitted only after
        the reply parses, every retry leaves a request written down and never
        answered -- a row that says "this may have been paid for" about a call
        we know was paid for, with no crash involved."""
        from cadence.observe.signals import ModelCalled, ModelRequested

        with cadence.recording() as tape:
            an_experiment(NONSENSE, IMPROVES).run()
        assert len(tape.of(ModelCalled)) == len(tape.of(ModelRequested)) == 2

    def test_every_request_is_answered_even_when_the_trial_is_given_up_on(self):
        from cadence.observe.signals import ModelCalled, ModelRequested

        with cadence.recording() as tape:
            an_experiment(*GIVES_UP).run()
        assert len(tape.of(ModelCalled)) == len(tape.of(ModelRequested))

    def test_a_call_that_never_returned_is_not_reported_as_answered(self):
        """The other half of the same pairing: a request that raised is a row
        that should stay open, because nobody knows whether it was billed."""
        from cadence.observe.signals import ModelCalled, ModelRequested

        with cadence.recording() as tape:
            an_experiment(TerminalModelError("401")).run()
        assert len(tape.of(ModelRequested)) == 1
        assert tape.of(ModelCalled) == []

    def test_a_trial_that_reached_the_sandbox_carries_its_verdict(self):
        from cadence.observe.signals import TrialMeasured

        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        assert tape.of(TrialMeasured)[0].verdict.is_scored

    def test_a_failed_run_still_reports_that_it_finished(self):
        from cadence.observe.signals import RunFinished

        with cadence.recording() as tape:
            an_experiment(TerminalModelError("401")).run()
        assert tape.of(RunFinished)[0].best is None


class TestABrokenVerifierStopsTheRun:
    """Handled since the beginning and never constructed, because with the
    candidate and the verifier in one process a non-zero exit could not be
    attributed. It can be now: the scoring command says so itself."""

    BROKE = (
        "Here.\n```python\nimport json\n"
        "print(json.dumps({'cadence_verifier_error': 'OPENAI_API_KEY unset'}))\n```"
    )

    def test_the_run_fails(self):
        assert an_experiment(self.BROKE).run().status == RunState.FAILED

    def test_it_says_the_scoring_command_was_at_fault(self):
        assert "scoring command" in an_experiment(self.BROKE).run().reason

    def test_it_does_not_spend_the_rest_of_the_budget(self):
        """Every later candidate would score the same way, so the budget
        would buy nothing but a confident wrong answer."""
        experiment = an_experiment(self.BROKE, budget=5)
        assert experiment.run().trials == 1


class TestARunSaysWhatItCost:
    """Best-found is incomparable across runs that spent differently, which
    is every comparison a person actually makes."""

    def test_it_counts_the_calls(self):
        assert an_experiment(IMPROVES).run().spend.calls == 1

    def test_it_counts_the_tokens(self):
        assert an_experiment(IMPROVES).run().spend.tokens > 0

    def test_a_retry_costs_another_call(self):
        assert an_experiment(NONSENSE, IMPROVES).run().spend.calls == 2

    def test_a_failed_run_still_says_what_it_spent(self):
        """The point of counting is the runs that go wrong."""
        report = an_experiment(*GIVES_UP, budget=1).run()
        assert report.spend.calls == Trial.max_attempts + 1

    def test_nothing_asked_for_is_nothing_spent(self):
        assert an_experiment(budget=0).run().spend.calls == 0
