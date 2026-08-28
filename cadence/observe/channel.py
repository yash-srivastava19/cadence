import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar

from blinker import ANY, Signal
from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Channel", "Emitter", "Fact", "Recorder"]


def _keeps_nothing(fact: "Fact") -> None:
    """The default recorder. A null object, so publish() never has to ask
    whether it has one."""


logger = logging.getLogger(__name__)

Unsubscribe = Callable[[], None]


def _now() -> datetime:
    return datetime.now(UTC)


class Channel:
    """Where facts about a run are announced.

    Two kinds of listener, because they want opposite things when they fail:

        subscribe   best effort. A broken progress bar must not end a run, so
                    the exception is logged and the run carries on.
        record      must succeed. If the event log cannot write the fact, the
                    run must not continue as though it had -- an audit trail
                    with holes in it is worse than none, because it is
                    trusted.

    The recorder is called directly rather than being connected as another
    subscriber. Blinker stops dispatching at the first receiver that raises,
    and the order it dispatches in is a dict-iteration accident rather than a
    guarantee -- so a raising recorder would silence an arbitrary subset of
    the other listeners.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._signal = Signal(name)
        self._recorder: Callable[[Fact], None] = _keeps_nothing

    def publish(self, fact: "Fact") -> None:
        # Recorded first, and allowed to raise: what has not been written
        # down has not happened, and nothing downstream should be told it has.
        self._recorder(fact)
        self._signal.send(type(fact), fact=fact)

    def record(self, handler: Callable[["Fact"], None]) -> Unsubscribe:
        """Register the one listener whose failure stops the run.

        One, not many: an event log is a single writer, and two of them would
        raise an ordering question with no good answer.
        """
        if self._recorder is not _keeps_nothing:
            raise RuntimeError(f"the {self.name} channel already has a recorder")
        self._recorder = handler

        def stop() -> None:
            self._recorder = _keeps_nothing

        return stop

    def subscribe(self, handler: Callable[[Any], None], to: Any = ANY) -> Unsubscribe:
        def receive(sender: Any, fact: Any) -> None:
            try:
                handler(fact)
            except Exception:
                logger.exception("subscriber %r failed handling %r", handler, sender)

        self._signal.connect(receive, sender=to, weak=False)
        return lambda: self._signal.disconnect(receive, sender=to)

    def recording(self, to: Any = ANY) -> "Recorder":
        return Recorder(self, to)


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    channel: ClassVar[Channel]

    at: datetime = Field(default_factory=_now)

    def __init_subclass__(cls, channel: Channel | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if channel is not None:
            cls.channel = channel

    def emit(self) -> None:
        self.channel.publish(self)


class Emitter:
    def __init__(self, **fields: Any) -> None:
        self.fields = fields

    def about(self, **more: Any) -> "Emitter":
        return Emitter(**self.fields, **more)

    def emit(self, fact: type[Fact], **fields: Any) -> None:
        fact(**self.fields, **fields).emit()


class Recorder:
    def __init__(self, channel: Channel, to: Any = ANY) -> None:
        self._channel = channel
        self._to = to
        self._facts: list[Fact] = []
        self._stop: Unsubscribe | None = None

    def __enter__(self) -> "Recorder":
        self._stop = self._channel.subscribe(self._facts.append, self._to)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._stop is not None:
            self._stop()
            self._stop = None

    def __iter__(self) -> Iterator[Fact]:
        return iter(self._facts)

    def __len__(self) -> int:
        return len(self._facts)

    def of(self, kind: type) -> list[Fact]:
        return [fact for fact in self._facts if isinstance(fact, kind)]
