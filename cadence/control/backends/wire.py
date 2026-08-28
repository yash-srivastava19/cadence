"""The OpenAI chat format, written down once.

Every provider cadence talks to speaks this dialect, so this file is the only
place in the codebase that knows a reply has "choices" in it. Parsing here
rather than reading the dict inline is what makes the difference between

    the provider returned no choices

and an empty completion that looks like the model wrote nothing useful, gets
retried three times, and bills you for the privilege.
"""

from typing import Any

from pydantic import Field

from cadence.core.types import NonBlank
from cadence.core.values import Parsed, Value

__all__ = ["ChatRequest", "ChatResponse", "Choice", "Message", "Usage"]


class ChatRequest(Value):
    model: NonBlank
    prompt: NonBlank
    temperature: float

    def as_json(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": self.prompt}],
            "temperature": self.temperature,
        }


class Message(Parsed):
    content: str = ""


class Choice(Parsed):
    message: Message = Message()


class Usage(Parsed):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ChatResponse(Parsed):
    # A reply with no choices is not a reply. Refusing it here is what stops a
    # provider fault from being reported as a badly written program.
    choices: tuple[Choice, ...] = Field(min_length=1)
    model: str | None = None
    usage: Usage = Usage()

    @property
    def text(self) -> str:
        return self.choices[0].message.content
