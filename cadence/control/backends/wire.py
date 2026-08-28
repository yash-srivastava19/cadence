"""The OpenAI chat format, written down once.

Every provider cadence talks to speaks this dialect, so this file is the only
place in the codebase that knows a reply has "choices" in it. Parsing here
rather than reading the dict inline is what makes the difference between

    the provider returned no choices

and an empty completion that looks like the model wrote nothing useful, gets
retried three times, and bills you for the privilege.
"""

from typing import Any

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
    # Null rather than absent, and both happen: an OpenAI-dialect provider
    # sends `"content": null` for a refusal, a filtered reply or a tool call.
    # A default only covers the absent case, so these are optional as well.
    content: str | None = None


class Choice(Parsed):
    message: Message | None = None


class Usage(Parsed):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ChatResponse(Parsed):
    # Required, but allowed to be empty. A body without the key at all is not
    # a reply and is terminal; a reply carrying no choices is a content filter
    # or a truncation, which is about this prompt and costs a trial.
    choices: tuple[Choice, ...]
    model: str | None = None
    usage: Usage | None = None

    @property
    def text(self) -> str:
        if not self.choices or self.choices[0].message is None:
            return ""
        return self.choices[0].message.content or ""

    @property
    def spent(self) -> Usage:
        return self.usage or Usage()

    @property
    def said_nothing(self) -> bool:
        """A well-formed reply carrying no completion.

        No choices, or a choice whose content is null -- the two spellings a
        provider uses for the same thing. Both cost a trial, not the run.
        """
        return not self.text
