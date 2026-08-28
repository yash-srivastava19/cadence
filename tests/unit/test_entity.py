import pytest
from statemachine import State, StateMachine
from statemachine.exceptions import TransitionNotAllowed

from cadence.lifecycle.entity import Entity
from cadence.lifecycle.states import TrialState


class TrialStateMachine(StateMachine):
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


class Trial(Entity, machine=TrialStateMachine):
    """A stand-in for the real one: every verb spelled out, nothing installed."""

    max_attempts = 2

    def __init__(self, status=None):
        self.status = status
        self.attempts = 0
        self.bind()

    @property
    def may_retry(self):
        return self._permits("retry")

    @property
    def may_measure(self):
        return self._permits("measure")

    def under_retry_budget(self):
        return self.attempts < self.max_attempts

    def prompt(self):
        self._fire("prompt")

    def retry(self):
        self._fire("retry")
        self.attempts += 1

    def apply_patch(self):
        self._fire("apply_patch")

    def measure(self):
        self._fire("measure")


def test_a_verb_moves_the_status():
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


def test_a_permission_can_be_asked_without_doing():
    trial = Trial()
    assert not trial.may_measure
    assert trial.status == TrialState.STARTED


def test_permissions_follow_a_status_loaded_from_storage():
    assert Trial(status=TrialState.MATERIALIZED).may_measure


def test_what_a_verb_does_happens_after_the_move_is_allowed():
    trial = Trial()
    trial.prompt()
    trial.retry()
    assert trial.attempts == 1


def test_a_refused_verb_leaves_the_entity_alone():
    trial = Trial()
    with pytest.raises(TransitionNotAllowed):
        trial.retry()
    assert trial.attempts == 0


def test_a_permission_honours_the_guard_on_its_transition():
    trial = Trial()
    trial.prompt()
    for _ in range(Trial.max_attempts):
        trial.retry()
    assert not trial.may_retry


def test_permitted_events_lists_the_way_out():
    trial = Trial(status=TrialState.GENERATED)
    assert trial.permitted_events() == {"apply_patch", "reject"}


def test_is_final_is_true_for_a_finished_entity_loaded_from_storage():
    assert not Trial().is_final
    assert Trial(status=TrialState.MEASURED).is_final


def test_using_the_machine_before_binding_says_so():
    class Unbound(Entity, machine=TrialStateMachine):
        def __init__(self):
            self.status = None

    with pytest.raises(RuntimeError, match="bind"):
        Unbound().permitted_events()
