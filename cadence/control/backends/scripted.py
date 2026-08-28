"""A backend with the answers written down in advance.

The default in .cadence, and the reason a full run works with no API key and
no network: tests and examples get a real Backend without a provider.
"""

from collections import deque

from cadence.core.dto import Completion
from cadence.errors import TerminalModelError

__all__ = ["Scripted"]


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
