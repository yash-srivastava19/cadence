"""Posting JSON, and deciding what a status code means.

Knows nothing about models or prompts. The only judgement it makes is whether
asking again could plausibly work.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, runtime_checkable

from cadence.core.values import Value
from cadence.errors import ModelError, RetryableModelError, TerminalModelError

__all__ = ["RETRYABLE", "Http", "HttpResponse", "Posts", "error_for", "timed"]

RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

P = ParamSpec("P")
T = TypeVar("T")


def timed(call: Callable[P, T]) -> Callable[P, tuple[T, float]]:
    """Return what the call returned, and how many milliseconds it took."""

    @wraps(call)
    def timing(*args: P.args, **kwargs: P.kwargs) -> tuple[T, float]:
        started = time.monotonic()
        return call(*args, **kwargs), (time.monotonic() - started) * 1000

    return timing


def error_for(status: int, detail: str) -> ModelError:
    """A 429 is worth backing off for. A 401 is worth nothing at all."""
    message = f"{status}: {detail}"
    if status in RETRYABLE:
        return RetryableModelError(message)
    return TerminalModelError(message)


class HttpResponse(Value):
    body: Mapping[str, Any]
    latency_ms: float


@runtime_checkable
class Posts(Protocol):
    """Somewhere to send a request and get a reply.

    A protocol rather than the class, because every seam in cadence that gets
    substituted is one: a test standing in for the network could satisfy Http
    in practice and not in the type, which is the sort of gap that makes a
    type checker useless exactly where it would help.
    """

    def post(
        self,
        url: str,
        request: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse: ...


class Http:
    def __init__(self, timeout: float = 300.0) -> None:
        self.timeout = timeout

    def post(
        self,
        url: str,
        request: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        body, latency_ms = self._send(url, request, headers or {})
        return HttpResponse(body=body, latency_ms=latency_ms)

    @timed
    def _send(
        self, url: str, request: Mapping[str, Any], headers: Mapping[str, str]
    ) -> Mapping[str, Any]:
        posted = urllib.request.Request(
            url,
            data=json.dumps(request).encode(),
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(posted, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise error_for(error.code, _detail(error)) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RetryableModelError(f"{url} did not answer: {error}") from error


def _detail(error: urllib.error.HTTPError) -> str:
    try:
        return error.read().decode()[:400]
    except Exception:
        return str(error)
