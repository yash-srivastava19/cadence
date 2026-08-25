import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cadence.exceptions import RetryableModelError, TerminalModelError
from cadence.http import Http
from cadence.control.backends.settings import Settings, known, settings_for

__all__ = [
    "Completion",
    "Backend",
    "Scripted",
    "Served",
    "Reliable",
    "known",
    "served",
    "Ollama",
    "Gemini",
]

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Completion(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    text: str
    model: NonBlank
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)

    @property
    def cost(self) -> dict[str, float]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
        }


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


class Reliable:
    """Retries and audits any backend, whether it speaks HTTP or an SDK."""

    def __init__(
        self,
        backend: "Backend",
        attempts: int = 3,
        backoff: float = 1.0,
        audit: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.backend = backend
        self.attempts = attempts
        self.backoff = backoff
        self.audit = audit

    @property
    def name(self) -> str:
        return self.backend.name

    def call(self, prompt: str) -> Completion:
        last: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                completion = self.backend.call(prompt)
                self._record(attempt, None)
                return completion
            except TerminalModelError as error:
                self._record(attempt, error)
                raise
            except RetryableModelError as error:
                last = error
                self._record(attempt, error)
                if attempt < self.attempts:
                    time.sleep(self.backoff * attempt)
        raise last

    def _record(self, attempt: int, error: Exception | None) -> None:
        if self.audit is not None:
            self.audit(
                {
                    "backend": self.name,
                    "attempt": attempt,
                    "error": None
                    if error is None
                    else f"{type(error).__name__}: {error}",
                }
            )


class Served:
    """Anything speaking the OpenAI dialect. The transport lives in Http."""

    def __init__(self, settings: Settings, http: Http | None = None) -> None:
        self.settings = settings
        self.http = http or Http(timeout=settings.timeout)

    @property
    def name(self) -> str:
        return self.settings.name

    def call(self, prompt: str) -> Completion:
        answer = self.http.post(
            f"{self.settings.url}/chat/completions",
            {
                "model": self.settings.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.settings.temperature,
            },
            self._headers(),
        )
        used = answer.get("usage") or {}
        choices = answer.get("choices") or [{}]
        message = choices[0].get("message") or {}
        return Completion(
            text=message.get("content") or "",
            model=answer.get("model") or self.settings.model,
            tokens_in=used.get("prompt_tokens", 0),
            tokens_out=used.get("completion_tokens", 0),
            latency_ms=answer.latency_ms,
        )

    def _headers(self) -> dict[str, str]:
        if not self.settings.needs_a_key:
            return {}
        return {"Authorization": f"Bearer {self.settings.demand_key()}"}


def served(
    name: str,
    http: Http | None = None,
    audit: Callable[[Mapping[str, Any]], None] | None = None,
    root=None,
    **overrides: Any,
) -> "Reliable":
    settings = settings_for(name, root=root, **overrides)
    return Reliable(
        Served(settings, http=http),
        attempts=settings.attempts,
        backoff=settings.backoff,
        audit=audit,
    )


def Ollama(**options) -> "Reliable":
    return served("ollama", **options)


def Gemini(**options) -> "Reliable":
    return served("gemini", **options)
