"""Retrying and auditing, for any backend, whether it speaks HTTP or an SDK."""

import time

from cadence.core.dto import Completion, Request
from cadence.core.ports import Audit, Backend
from cadence.errors import RetryableModelError, TerminalModelError, UnusableReply

__all__ = ["Reliable", "Silent"]


class Silent:
    """Records nothing.

    A null audit rather than an optional one, so Reliable never asks whether
    it has somewhere to report to.
    """

    def succeeded(self, backend: str, attempt: int) -> None: ...

    def failed(self, backend: str, attempt: int, error: Exception) -> None: ...


class Reliable:
    def __init__(
        self,
        backend: Backend,
        attempts: int = 3,
        backoff: float = 1.0,
        audit: Audit | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("a call needs at least one attempt")
        self.backend = backend
        self.attempts = attempts
        self.backoff = backoff
        self.audit: Audit = audit or Silent()

    @property
    def name(self) -> str:
        return self.backend.name

    def call(self, request: Request) -> Completion:
        for attempt in range(1, self.attempts + 1):
            try:
                completion = self.backend.call(request)
            except (TerminalModelError, UnusableReply) as error:
                # An unusable reply is not retried here -- the trial asks
                # again, which is a fresh call. It is audited here because
                # this is the only place that knows a call was paid for.
                self.audit.failed(self.name, attempt, error)
                raise
            except RetryableModelError as error:
                self.audit.failed(self.name, attempt, error)
                if attempt == self.attempts:
                    raise
                time.sleep(self.backoff * attempt)
            else:
                self.audit.succeeded(self.name, attempt)
                return completion
        raise AssertionError("unreachable: attempts is at least 1")
