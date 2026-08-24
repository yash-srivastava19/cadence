from cadence.backends import Scripted
from cadence.exceptions import TerminalModelError
from cadence.experiment import Experiment, Report
from cadence.methods import Evolution
from cadence.model import Model
from cadence.objectives import WeightedSum
from cadence.runner import TrialRunner
from cadence.sandbox import Subprocess
from cadence.signals import cadence
from cadence.states import RunState

BASELINE = "print('value: 0')"


def rewritten(program):
    return f"Here is the new program.\n```python\n{program}\n```"


IMPROVES = rewritten("print('value: 9')")
SILENT = rewritten("print('nothing to report')")
CRASHES = rewritten("raise ValueError('the evolved code is broken')")
NONSENSE = "I would change the loop, but here is prose instead."


def an_experiment(*responses, budget=1, metrics=None):
    return Experiment(
        run_id="h1",
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
            "ModelCalled",
            "ProposalReceived",
            "TrialMeasured",
            "RunFinished",
        ]

    def test_every_event_names_the_run(self):
        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        assert {fact.run_id for fact in tape} == {"h1"}

    def test_the_model_call_reports_what_it_cost(self):
        from cadence.signals import ModelCalled

        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        called = tape.of(ModelCalled)[0]
        assert called.tokens_in > 0 and called.tokens_out > 0

    def test_the_measured_event_carries_the_verdict(self):
        from cadence.signals import TrialMeasured

        with cadence.recording() as tape:
            an_experiment(IMPROVES).run()
        assert tape.of(TrialMeasured)[0].verdict.is_scored

    def test_an_abandoned_trial_is_visible_on_the_tape(self):
        from cadence.signals import TrialAbandoned

        with cadence.recording() as tape:
            an_experiment(NONSENSE).run()
        assert "```python block" in tape.of(TrialAbandoned)[0].reason


class TestFailingWell:
    def test_an_unparseable_answer_abandons_the_trial_not_the_run(self):
        report = an_experiment(NONSENSE).run()
        assert report.status == RunState.FINISHED
        assert report.scored == 0

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
