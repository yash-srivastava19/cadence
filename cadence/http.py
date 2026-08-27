import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from cadence.exceptions import RetryableModelError, TerminalModelError

__all__ = ["RETRYABLE", "Answer", "Http"]

RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class Answer(dict):
    """A decoded JSON body, with how long the call took."""

    latency_ms: float = 0.0


class Http:
    def __init__(self, timeout: float = 300.0) -> None:
        self.timeout = timeout

    def post(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Answer:
        started = time.monotonic()
        answer = self._once(url, payload, headers or {})
        answer.latency_ms = (time.monotonic() - started) * 1000
        return answer

    def _once(
        self, url: str, payload: Mapping[str, Any], headers: Mapping[str, str]
    ) -> Answer:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return Answer(json.loads(response.read() or b"{}"))
        except urllib.error.HTTPError as error:
            raise _classify(error.code, _body(error)) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RetryableModelError(f"{url} did not answer: {error}") from error


def _classify(status: int, detail: str) -> Exception:
    message = f"{status}: {detail}"
    return (
        RetryableModelError(message)
        if status in RETRYABLE
        else TerminalModelError(message)
    )


def _body(error: "urllib.error.HTTPError") -> str:
    try:
        return error.read().decode()[:400]
    except Exception:
        return str(error)
