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

BASELINE = "def solve(a, b):\n    return 0"


class Adder:
    entry_point = "solve"
    baseline = BASELINE

    def inputs(self, seed):
        return (seed + 1, seed + 2)

    def score(self, output, inputs):
        return {"closeness": -float(abs(sum(inputs) - output))}


class BrokenVerifier(Adder):
    def score(self, output, inputs):
        raise ZeroDivisionError("the scoring script is wrong")


def answer(body):
    return (
        "```diff\n"
        "--- a/s.py\n"
        "+++ b/s.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def solve(a, b):\n"
        "-    return 0\n"
        f"+    {body}\n"
        "```"
    )


IMPROVES = answer("return a + b")
NONSENSE = "I would change the loop, but here is prose instead."


def an_experiment(task=None, budget=1, *responses):
    return Experiment(
        run_id="h1",
        method=Evolution(objective=WeightedSum(closeness=1.0), seed=0),
        model=Model(backend=Scripted(*responses)),
        runner=TrialRunner(task=task or Adder(), sandbox=Subprocess(), seeds=(0,)),
        seeds=[BASELINE],
        budget=budget,
    )


class TestAFullOfflineRun:
    def test_it_finishes(self):
        report = an_experiment(None, 1, IMPROVES).run()
        assert report.status == RunState.FINISHED

    def test_it_scores_the_candidate_it_produced(self):
        report = an_experiment(None, 1, IMPROVES).run()
        assert report.scored == 1

    def test_it_names_a_best(self):
        report = an_experiment(None, 1, IMPROVES).run()
        assert report.best is not None

    def test_the_improvement_is_real(self):
        report = an_experiment(None, 1, IMPROVES).run()
        assert report.metrics["closeness"] == 0.0

    def test_it_runs_the_whole_budget(self):
        report = an_experiment(None, 3, IMPROVES, IMPROVES, IMPROVES).run()
        assert report.trials == 3

    def test_the_report_survives_json(self):
        report = an_experiment(None, 1, IMPROVES).run()
        assert Report.model_validate_json(report.model_dump_json()) == report


class TestTheRunIsTraceable:
    def test_the_tape_reads_start_to_finish(self):
        with cadence.recording() as tape:
            an_experiment(None, 1, IMPROVES).run()
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
            an_experiment(None, 1, IMPROVES).run()
        assert {fact.run_id for fact in tape} == {"h1"}

    def test_the_model_call_reports_what_it_cost(self):
        from cadence.signals import ModelCalled

        with cadence.recording() as tape:
            an_experiment(None, 1, IMPROVES).run()
        called = tape.of(ModelCalled)[0]
        assert called.tokens_in > 0 and called.tokens_out > 0

    def test_the_measured_event_carries_the_verdict(self):
        from cadence.signals import TrialMeasured

        with cadence.recording() as tape:
            an_experiment(None, 1, IMPROVES).run()
        assert tape.of(TrialMeasured)[0].verdict.is_scored

    def test_an_abandoned_trial_is_visible_on_the_tape(self):
        from cadence.signals import TrialAbandoned

        with cadence.recording() as tape:
            an_experiment(None, 1, NONSENSE).run()
        assert "diff block" in tape.of(TrialAbandoned)[0].reason


class TestFailingWell:
    def test_an_unparseable_answer_abandons_the_trial_not_the_run(self):
        report = an_experiment(None, 1, NONSENSE).run()
        assert report.status == RunState.FINISHED
        assert report.scored == 0

    def test_a_broken_verifier_fails_the_run(self):
        report = an_experiment(BrokenVerifier(), 1, IMPROVES).run()
        assert report.status == RunState.FAILED

    def test_a_broken_verifier_says_what_to_fix(self):
        report = an_experiment(BrokenVerifier(), 1, IMPROVES).run()
        assert "ZeroDivisionError" in report.reason

    def test_a_broken_verifier_does_not_report_a_best(self):
        report = an_experiment(BrokenVerifier(), 1, IMPROVES).run()
        assert report.best is None

    def test_running_out_of_backend_ends_the_run(self):
        report = an_experiment(None, 2, IMPROVES).run()
        assert report.status == RunState.FAILED
        assert isinstance(report.reason, str)

    def test_a_terminal_model_error_is_not_retried_into_the_ground(self):
        experiment = an_experiment(None, 1, TerminalModelError("401"))
        report = experiment.run()
        assert report.status == RunState.FAILED
        assert len(experiment.model.backend.prompts) == 1
