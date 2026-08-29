"""Talking to a provider that speaks the OpenAI chat dialect.

Adding a provider is a row in providers.yml. This class is what that row
becomes, and it is the same class for every one of them.
"""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from cadence.control.backends.http import Http, Posts
from cadence.control.backends.reliable import Reliable
from cadence.control.backends.settings import Settings, settings_for
from cadence.control.backends.wire import ChatRequest, ChatResponse, Usage
from cadence.core.dto import Completion
from cadence.core.ports import Audit
from cadence.errors import EmptyReply, TerminalModelError

__all__ = ["OpenAIDialect", "chat_backend"]


class OpenAIDialect:
    """One provider. The transport is Http's problem, the format is wire's."""

    def __init__(self, settings: Settings, http: Posts | None = None) -> None:
        self.settings = settings
        self.http = http or Http(timeout=settings.timeout)

    @property
    def name(self) -> str:
        return self.settings.name

    def call(self, prompt: str) -> Completion:
        request = ChatRequest(
            model=self.settings.model,
            prompt=prompt,
            temperature=self.settings.temperature,
        )
        answer = self.http.post(
            f"{self.settings.url}/chat/completions",
            request.as_json(),
            self.settings.headers(),
        )
        reply = self._read(answer.body)
        if reply.said_nothing:
            raise EmptyReply(f"{self.name} returned a reply with no completion in it")
        model = reply.model or self.settings.model
        return Completion(
            text=reply.text,
            model=model,
            tokens_in=reply.spent.prompt_tokens,
            tokens_out=reply.spent.completion_tokens,
            latency_ms=answer.latency_ms,
            # Priced here because this is the only place that knows both the
            # tokens and which provider quoted for them. The model the reply
            # names, not the one we asked for: a provider that served
            # something else billed for what it served.
            cost_usd=self._priced(model, reply.spent),
        )

    def _priced(self, model: str, spent: Usage) -> float | None:
        price = self.settings.price_of(model)
        if price is None:
            return None
        return price.of(spent.prompt_tokens, spent.completion_tokens)

    def _read(self, body: Any) -> ChatResponse:
        try:
            return ChatResponse.model_validate(body)
        except ValidationError as error:
            # Terminal, not retryable: a provider that answers in a shape we
            # cannot read will answer the same way next time, and blaming the
            # model for it costs three more calls to learn nothing.
            raise TerminalModelError(
                f"{self.name} returned a body cadence could not read: {error}"
            ) from error


def chat_backend(
    name: str,
    http: Posts | None = None,
    audit: Audit | None = None,
    root: Path | None = None,
    **overrides: Any,
) -> Reliable:
    settings = settings_for(name, root=root, **overrides)
    return Reliable(
        OpenAIDialect(settings, http=http),
        attempts=settings.attempts,
        backoff=settings.backoff,
        audit=audit,
    )
