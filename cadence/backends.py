import os
import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cadence.exceptions import RetryableModelError, TerminalModelError
from cadence.http import Http

__all__ = [
    "Completion",
    "Backend",
    "Scripted",
    "Served",
    "Reliable",
    "Provider",
    "PROVIDERS",
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


class Provider(Protocol):
    name: str

    def request(
        self, prompt: str
    ) -> tuple[str, Mapping[str, Any], Mapping[str, str]]: ...

    def read(self, answer: Mapping[str, Any]) -> tuple[str, str, int, int]: ...


class Served:
    """Any provider reached over HTTP. The transport lives in Http, not here."""

    def __init__(self, provider: Provider, http: Http | None = None, **options) -> None:
        self.provider = provider
        self.http = http or Http(**options)

    @property
    def name(self) -> str:
        return self.provider.name

    def call(self, prompt: str) -> Completion:
        url, payload, headers = self.provider.request(prompt)
        answer = self.http.post(url, payload, headers)
        text, model, tokens_in, tokens_out = self.provider.read(answer)
        return Completion(
            text=text,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=answer.latency_ms,
        )


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        model: str = "qwen3-agent:latest",
        host: str | None = None,
        temperature: float = 0.8,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.host = (
            host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        ).rstrip("/")

    def request(self, prompt):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": self.temperature},
        }
        return f"{self.host}/api/generate", payload, {}

    def read(self, answer):
        return (
            answer.get("response", ""),
            answer.get("model", self.model),
            answer.get("prompt_eval_count", 0) or 0,
            answer.get("eval_count", 0) or 0,
        )


class GeminiProvider:
    name = "gemini"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        model: str = "gemini-3.6-flash",
        api_key: str | None = None,
        temperature: float = 0.8,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )

    def request(self, prompt):
        if not self.api_key:
            raise TerminalModelError("no API key; set GEMINI_API_KEY or pass api_key")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": self.temperature},
        }
        url = f"{self.endpoint}/{self.model}:generateContent"
        return url, payload, {"x-goog-api-key": self.api_key}

    def read(self, answer):
        candidates = answer.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts") or []
        used = answer.get("usageMetadata", {})
        return (
            "".join(part.get("text", "") for part in parts),
            answer.get("modelVersion", self.model),
            used.get("promptTokenCount", 0),
            used.get("candidatesTokenCount", 0),
        )


PROVIDERS: Mapping[str, type] = {"ollama": OllamaProvider, "gemini": GeminiProvider}


def served(
    name: str,
    http: Http | None = None,
    attempts: int = 3,
    backoff: float = 1.0,
    audit: Callable[[Mapping[str, Any]], None] | None = None,
    **options,
) -> Reliable:
    if name not in PROVIDERS:
        raise TerminalModelError(
            f"no provider named {name!r}; known: {', '.join(sorted(PROVIDERS))}"
        )
    inner = Served(PROVIDERS[name](**options), http=http)
    return Reliable(inner, attempts=attempts, backoff=backoff, audit=audit)


def Ollama(http: Http | None = None, **options) -> Reliable:
    return served("ollama", http, **options)


def Gemini(http: Http | None = None, **options) -> Reliable:
    return served("gemini", http, **options)
