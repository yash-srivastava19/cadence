from collections import deque
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cadence.exceptions import TerminalModelError

__all__ = ["Completion", "Backend", "Scripted"]

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Completion(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    text: str
    model: NonBlank
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


@runtime_checkable
class Backend(Protocol):
    @property
    def name(self) -> str: ...

    def call(self, prompt: str) -> Completion: ...


class Scripted:
    name = "scripted"
    model = "scripted-1"

    def __init__(self, *responses: str | Exception) -> None:
        self._remaining = deque(responses)
        self.prompts: list[str] = []

    @property
    def remaining(self) -> int:
        return len(self._remaining)

    def call(self, prompt: str) -> Completion:
        self.prompts.append(prompt)
        if not self._remaining:
            raise TerminalModelError("the scripted backend ran out of responses")
        answer = self._remaining.popleft()
        if isinstance(answer, Exception):
            raise answer
        return Completion(
            text=answer,
            model=self.model,
            tokens_in=len(prompt.split()),
            tokens_out=len(answer.split()),
            latency_ms=0.0,
        )
