import pytest
from statemachine import State, StateMachine
from statemachine.exceptions import TransitionNotAllowed

from cadence.stateful import Stateful
from cadence.states import TrialState


class TrialMachine(StateMachine):
    started = State(value=TrialState.STARTED, initial=True)
    prompted = State(value=TrialState.PROMPTED)
    generated = State(value=TrialState.GENERATED)
    materialized = State(value=TrialState.MATERIALIZED)
    measured = State(value=TrialState.MEASURED, final=True)
    unusable = State(value=TrialState.UNUSABLE, final=True)

    prompt = started.to(prompted)
    retry = prompted.to.itself(cond="under_retry_budget")
    generate = prompted.to(generated)
    apply_patch = generated.to(materialized)
    reject = generated.to(unusable)
    measure = materialized.to(measured)


class Trial(Stateful, machine=TrialMachine):
    max_attempts = 2

    def __init__(self, status=None):
        self.status = status
        self.attempts = 0
        self.bind()

    def under_retry_budget(self):
        return self.attempts < self.max_attempts

    def on_retry(self):
        self.attempts += 1


def test_events_are_methods_on_the_entity():
    trial = Trial()
    trial.prompt()
    assert trial.status == TrialState.PROMPTED


def test_status_starts_at_the_initial_state():
    assert Trial().status == TrialState.STARTED


def test_an_entity_loaded_from_storage_resumes_where_it_was():
    trial = Trial(status=TrialState.GENERATED)
    trial.apply_patch()
    assert trial.status == TrialState.MATERIALIZED


def test_status_is_a_str_enum_so_storage_sees_a_string():
    assert Trial().status == "started"


def test_an_illegal_transition_raises():
    with pytest.raises(TransitionNotAllowed):
        Trial().measure()


def test_each_state_gets_a_predicate():
    trial = Trial()
    assert trial.is_started
    assert not trial.is_measured
    trial.prompt()
    assert trial.is_prompted


def test_each_event_gets_a_permission():
    trial = Trial()
    assert trial.may_prompt
    assert not trial.may_measure


def test_predicates_follow_a_status_loaded_from_storage():
    trial = Trial(status=TrialState.GENERATED)
    assert trial.is_generated
    assert trial.may_apply_patch
    assert not trial.may_prompt


def test_callbacks_resolve_against_the_entity():
    trial = Trial()
    trial.prompt()
    trial.retry()
    assert trial.attempts == 1


def test_a_permission_honours_the_guard_on_its_transition():
    trial = Trial()
    trial.prompt()
    for _ in range(Trial.max_attempts):
        trial.retry()
    assert not trial.may_retry


def test_a_name_the_entity_already_uses_is_refused():
    with pytest.raises(TypeError, match="is_started"):

        class Shadowed(Stateful, machine=TrialMachine):
            is_started = True


def test_permitted_events_lists_the_way_out():
    trial = Trial(status=TrialState.GENERATED)
    assert trial.permitted_events() == {"apply_patch", "reject"}


def test_can_takes_an_event_name_that_is_not_known_until_runtime():
    assert Trial().can("prompt")
    assert not Trial().can("measure")


def test_is_final_is_true_for_a_finished_entity_loaded_from_storage():
    assert not Trial().is_final
    assert Trial(status=TrialState.MEASURED).is_final


def test_using_the_machine_before_binding_says_so():
    class Unbound(Stateful, machine=TrialMachine):
        def __init__(self):
            self.status = None

    with pytest.raises(RuntimeError, match="bind"):
        Unbound().can("prompt")
