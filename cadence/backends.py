import json
import time
import urllib.error
import urllib.request
import os
import re
from collections import deque
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cadence.exceptions import RetryableModelError, TerminalModelError

__all__ = ["Completion", "Backend", "Scripted", "Ollama"]

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


THINKING = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class Ollama:
    name = "ollama"

    def __init__(
        self,
        model: str = "qwen3-agent:latest",
        host: str | None = None,
        seconds: float = 300.0,
        temperature: float = 0.8,
    ) -> None:
        self.model = model
        self.host = (
            host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        ).rstrip("/")
        self.seconds = seconds
        self.temperature = temperature

    def call(self, prompt: str) -> Completion:
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": self.temperature},
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.seconds) as response:
                answer = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise _classified(error) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RetryableModelError(f"{self.host} did not answer: {error}") from error

        return Completion(
            text=THINKING.sub("", answer.get("response", "")),
            model=answer.get("model", self.model),
            tokens_in=answer.get("prompt_eval_count", 0),
            tokens_out=answer.get("eval_count", 0),
            latency_ms=(time.monotonic() - started) * 1000,
        )


def _classified(error: "urllib.error.HTTPError") -> Exception:
    if error.code == 404:
        return TerminalModelError(
            f"no such model; pull it with `ollama pull` ({error})"
        )
    if error.code in (408, 429) or error.code >= 500:
        return RetryableModelError(str(error))
    return TerminalModelError(str(error))
