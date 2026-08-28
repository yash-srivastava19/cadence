"""The base for anything whose status is a state machine.

The division of labour: the machine owns which moves are legal and what
guards them; the entity spells out its own verbs, one short method each.

    def measure(self, verdict: Verdict) -> None:
        self._fire("measure", verdict=verdict)
        self.verdict = verdict

That method could be installed automatically -- the library will do it -- and
this class used to. It stopped because an entity whose verbs exist only at
runtime cannot be read: `trial.measure(...)` appears nowhere in Trial, no
editor will jump to it, and no type checker will admit it exists. Twenty of
the thirty-four type errors in this package were that one decision.

What stays generic is what is genuinely uniform: binding, asking which moves
are permitted, and whether there are any left.
"""

from typing import Any, ClassVar

from statemachine import StateMachine

__all__ = ["Entity"]


class Entity:
    machine_class: ClassVar[type[StateMachine]]
    state_field: ClassVar[str] = "status"

    def __init_subclass__(
        cls,
        machine: type[StateMachine] | None = None,
        state_field: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if state_field is not None:
            cls.state_field = state_field
        if machine is not None:
            cls.machine_class = machine

    def bind(self) -> None:
        """Attach the machine to this instance. Call it from __init__.

        Also called by storage when an entity is loaded, so a row read back
        comes out with a live machine rather than a bare string.
        """
        object.__setattr__(
            self, "_machine", self.machine_class(self, state_field=self.state_field)
        )

    @property
    def machine(self) -> StateMachine:
        machine = getattr(self, "_machine", None)
        if machine is None:
            raise RuntimeError(
                f"{type(self).__name__}.bind() was never called; call it from __init__"
            )
        return machine

    def _fire(self, event: str, **fields: Any) -> None:
        """Make the move, or raise TransitionNotAllowed.

        Every verb on every entity goes through here, so "the status only ever
        changes by a declared transition" is one line to check rather than a
        habit to maintain.
        """
        self.machine.send(event, **fields)

    def _permits(self, event: str) -> bool:
        return event in self.permitted_events()

    def permitted_events(self) -> frozenset[str]:
        return frozenset(event.id for event in self.machine.enabled_events())

    @property
    def is_final(self) -> bool:
        """No permitted events remain. Nothing more will happen to this."""
        return not self.permitted_events()
