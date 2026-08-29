from collections.abc import Callable
from hashlib import sha256

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cadence.control.storage import model_calls
from cadence.core.dto import Completion, Recalled
from cadence.core.ports import Calls
from cadence.errors import PromptChanged

__all__ = ["Recorded", "Remembered", "key_for", "through"]


class Remembered:
    def __init__(self) -> None:
        self.calls: dict[str, Recalled] = {}

    def get(self, key: str) -> Recalled | None:
        return self.calls.get(key)

    def put(self, key: str, recalled: Recalled) -> None:
        self.calls[key] = recalled

    def __len__(self) -> int:
        return len(self.calls)


class Recorded:
    """The replay store, backed by the model_calls the journal wrote.

    Read-only by design. put() does nothing because the journal is already
    recording the call -- two writers to one table would be two accounts of
    the same event, and the interesting question is which one is wrong.

    Only rows marked done are offered back. One left in_flight is a call that
    may have been paid for and whose answer nobody saw, which is a different
    situation and not one a cache can help with.
    """

    def __init__(self, session: Session, run_id: str) -> None:
        self.session = session
        self.run_id = run_id

    def get(self, key: str) -> Recalled | None:
        row = (
            self.session.execute(
                sa.select(model_calls)
                .where(model_calls.c.id == key)
                .where(model_calls.c.run_id == self.run_id)
                .where(model_calls.c.status == "done")
            )
            .mappings()
            .one_or_none()
        )
        if row is None or row["response"] is None:
            return None
        return Recalled(
            prompt_digest=row["request_hash"],
            completion=Completion(
                text=row["response"],
                model=row["model"] or "recorded",
                tokens_in=row["tokens_in"] or 0,
                tokens_out=row["tokens_out"] or 0,
                latency_ms=row["latency_ms"] or 0.0,
            ),
        )

    def put(self, key: str, recalled: Recalled) -> None:
        """Nothing: the journal writes what this reads."""


def key_for(run_id: str, index: int, attempt: int = 0) -> str:
    # A retry asks the same question again, so it must not replay the answer
    # that already failed to parse.
    return f"{run_id}/{index}" if not attempt else f"{run_id}/{index}#{attempt}"


def digest(prompt: str) -> str:
    return sha256(prompt.encode()).hexdigest()[:16]


def through(
    calls: Calls,
    key: str,
    prompt: str,
    call: Callable[[], Completion],
) -> tuple[Completion, bool]:
    seen = calls.get(key)
    if seen is not None:
        if seen.prompt_digest != digest(prompt):
            raise PromptChanged(
                f"{key} was recorded against a different prompt;"
                " the run is not reproducing what it did before"
            )
        return seen.completion, True
    completion = call()
    calls.put(key, Recalled(prompt_digest=digest(prompt), completion=completion))
    return completion, False
