from collections.abc import Callable
from hashlib import sha256

from cadence.core.dto import Completion, Recalled
from cadence.core.ports import Calls
from cadence.errors import PromptChanged

__all__ = ["Remembered", "key_for", "through"]


class Remembered:
    def __init__(self) -> None:
        self.calls: dict[str, Recalled] = {}

    def get(self, key: str) -> Recalled | None:
        return self.calls.get(key)

    def put(self, key: str, recalled: Recalled) -> None:
        self.calls[key] = recalled

    def __len__(self) -> int:
        return len(self.calls)


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
