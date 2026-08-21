from typing import ClassVar

from statemachine import StateMachine

__all__ = ["Stateful"]


def _event_ids(machine: type[StateMachine]) -> frozenset[str]:
    return frozenset(
        event.id
        for state in machine.states
        for event in state.transitions.unique_events
    )


class Stateful:
    machine_class: ClassVar[type[StateMachine]]
    state_field: ClassVar[str] = "status"

    def __init_subclass__(
        cls,
        machine: type[StateMachine] | None = None,
        state_field: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if state_field is not None:
            cls.state_field = state_field
        if machine is None:
            return
        cls.machine_class = machine
        for state in machine.states:
            cls._install(f"is_{state.id}", _is_state(state.id))
        for event in _event_ids(machine):
            cls._install(f"may_{event}", _may_fire(event))

    @classmethod
    def _install(cls, name: str, prop: property) -> None:
        if hasattr(cls, name):
            raise TypeError(
                f"{cls.__name__} already defines {name!r}, "
                f"which {cls.machine_class.__name__} needs"
            )
        setattr(cls, name, prop)

    def bind(self) -> None:
        machine = self.machine_class(self, state_field=self.state_field)
        machine.bind_events_to(self)
        object.__setattr__(self, "_machine", machine)

    @property
    def machine(self) -> StateMachine:
        machine = getattr(self, "_machine", None)
        if machine is None:
            raise RuntimeError(
                f"{type(self).__name__}.bind() was never called; call it from __init__"
            )
        return machine

    def can(self, event: str) -> bool:
        return event in self.permitted_events()

    def permitted_events(self) -> frozenset[str]:
        return frozenset(event.id for event in self.machine.enabled_events())

    @property
    def is_final(self) -> bool:
        return not self.permitted_events()


def _is_state(state_id: str) -> property:
    return property(lambda self: getattr(self.machine, state_id).is_active)


def _may_fire(event_id: str) -> property:
    return property(lambda self: self.can(event_id))
