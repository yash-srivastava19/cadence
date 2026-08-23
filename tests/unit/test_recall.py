import pytest

from cadence.backends import Scripted
from cadence.experiment import Experiment
from cadence.methods import Evolution
from cadence.model import Model
from cadence.objectives import WeightedSum
from cadence.recall import (
    Calls,
    PromptChanged,
    Remembered,
    key_for,
    through,
)
from cadence.runner import TrialRunner
from cadence.sandbox import Subprocess
from cadence.signals import ModelCalled, cadence
from cadence.states import RunState

BASELINE = "print('value: 0')"
ANSWER = (
    "```diff\n--- a/prog.py\n+++ b/prog.py\n@@ -1,1 +1,1 @@\n"
    "-print('value: 0')\n+print('value: 9')\n```"
)


def a_completion(text="hello"):
    return Scripted(text).call("a prompt")


class TestTheStore:
    def test_remembered_satisfies_the_port(self):
        assert isinstance(Remembered(), Calls)

    def test_a_key_names_a_run_and_a_trial(self):
        assert key_for("h1", 3) == "h1/3"

    def test_the_same_position_gives_the_same_key(self):
        assert key_for("h1", 3) == key_for("h1", 3)


class TestPayingOnlyOnce:
    def test_the_first_call_goes_through(self):
        calls, spent = Remembered(), []
        completion, replayed = through(
            calls, "h1/0", "p", lambda: spent.append(1) or a_completion()
        )
        assert not replayed
        assert len(spent) == 1

    def test_the_second_call_does_not(self):
        calls, spent = Remembered(), []

        def make():
            spent.append(1)
            return a_completion()

        through(calls, "h1/0", "p", make)
        completion, replayed = through(calls, "h1/0", "p", make)
        assert replayed
        assert len(spent) == 1

    def test_a_replay_returns_what_was_recorded(self):
        calls = Remembered()
        first, _ = through(calls, "h1/0", "p", lambda: a_completion("the answer"))
        second, _ = through(calls, "h1/0", "p", lambda: a_completion("something else"))
        assert second == first

    def test_a_different_trial_is_a_different_call(self):
        calls, spent = Remembered(), []

        def make():
            spent.append(1)
            return a_completion()

        through(calls, "h1/0", "p", make)
        through(calls, "h1/1", "p", make)
        assert len(spent) == 2

    def test_the_same_key_with_a_different_prompt_is_refused(self):
        calls = Remembered()
        through(calls, "h1/0", "the prompt", a_completion)
        with pytest.raises(PromptChanged, match="not reproducing"):
            through(calls, "h1/0", "a different prompt", a_completion)


class TestAModelThatRemembers:
    def test_it_calls_the_backend_once_for_one_key(self):
        model = Model(backend=Scripted(ANSWER), calls=Remembered())
        directive = _a_directive()
        model.propose(directive, key="h1/0")
        model.propose(directive, key="h1/0")
        assert len(model.backend.prompts) == 1

    def test_it_says_when_it_replayed(self):
        model = Model(backend=Scripted(ANSWER), calls=Remembered())
        directive = _a_directive()
        assert not model.propose(directive, key="h1/0").replayed
        assert model.propose(directive, key="h1/0").replayed

    def test_without_a_store_nothing_is_remembered(self):
        model = Model(backend=Scripted(ANSWER, ANSWER))
        directive = _a_directive()
        model.propose(directive)
        model.propose(directive)
        assert len(model.backend.prompts) == 2


class TestResumingARunCostsNothing:
    def test_the_second_run_makes_no_model_calls(self):
        calls = Remembered()
        first = _an_experiment(calls, Scripted(ANSWER, ANSWER))
        assert first.run().status == RunState.FINISHED

        second = _an_experiment(calls, Scripted())
        report = second.run()
        assert report.status == RunState.FINISHED
        assert second.model.backend.prompts == []

    def test_it_reaches_the_same_answer(self):
        calls = Remembered()
        first = _an_experiment(calls, Scripted(ANSWER, ANSWER)).run()
        second = _an_experiment(calls, Scripted()).run()
        assert second.best == first.best
        assert second.program == first.program

    def test_the_tape_marks_the_call_as_replayed(self):
        calls = Remembered()
        _an_experiment(calls, Scripted(ANSWER, ANSWER)).run()
        with cadence.recording() as tape:
            _an_experiment(calls, Scripted()).run()
        assert all(fact.replayed for fact in tape.of(ModelCalled))

    def test_the_first_run_is_not_marked_replayed(self):
        with cadence.recording() as tape:
            _an_experiment(Remembered(), Scripted(ANSWER, ANSWER)).run()
        assert not any(fact.replayed for fact in tape.of(ModelCalled))


def _a_directive():
    from cadence.interfaces import Directive

    return Directive(parent="abc", code=BASELINE, hint="try something")


def _an_experiment(calls, backend, budget=2):
    return Experiment(
        run_id="resumable",
        method=Evolution(objective=WeightedSum(value=1.0)),
        model=Model(backend=backend, calls=calls),
        runner=TrialRunner(
            program="prog.py",
            command=("python", "prog.py"),
            metrics={"value": "maximize"},
            sandbox=Subprocess(),
            seeds=(0,),
        ),
        seeds=[BASELINE],
        budget=budget,
    )
