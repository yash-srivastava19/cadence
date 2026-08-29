"""Posting JSON, and deciding what a status code means.

Knows nothing about models or prompts. The only judgement it makes is whether
asking again could plausibly work.
"""

import http.client
import json
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from functools import wraps
from itertools import zip_longest
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


#: Getting a connection, all addresses together. A model may think for
#: minutes; reaching a host either works soon or will not.
CONNECT_SECONDS = 10.0

#: And any one address, so a dead one leaves time for the next.
ATTEMPT_SECONDS = 3.0


class Http:
    def __init__(
        self, timeout: float = 300.0, connect_timeout: float = CONNECT_SECONDS
    ) -> None:
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self._opener = _opener_for(connect_timeout, timeout)

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
            with self._opener.open(posted, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raise error_for(error.code, _detail(error)) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RetryableModelError(f"{url} did not answer: {error}") from error


def _opener_for(connect: float, read: float) -> urllib.request.OpenerDirector:
    """An opener that budgets connecting and reading separately.

    urlopen takes one timeout and uses it for both, so a long read budget --
    which a slow model needs -- becomes a long wait on a host that never
    answers.
    """

    class Connection(http.client.HTTPSConnection):
        def connect(self) -> None:
            self._create_connection = _within(connect)
            super().connect()
            self.sock.settimeout(read)  # connected; now it is the model's time

    class Plain(http.client.HTTPConnection):
        def connect(self) -> None:
            self._create_connection = _within(connect)
            super().connect()
            self.sock.settimeout(read)

    class Secure(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(Connection, req)

    class Insecure(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(Plain, req)

    return urllib.request.build_opener(Secure, Insecure)


def _within(budget: float) -> Callable[..., socket.socket]:
    """The first address that answers, within one budget for all of them.

    socket.create_connection spends the whole timeout on each address, and a
    host with eight of them turns ten seconds into eighty.
    """

    def connect(address, timeout=None, source_address=None) -> socket.socket:
        deadline = time.monotonic() + budget
        host, port = address[0], address[1]
        last: OSError | None = None
        for family, kind, proto, _, where in _by_turns(
            socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        ):
            left = deadline - time.monotonic()
            if left <= 0:
                break
            sock = socket.socket(family, kind, proto)
            try:
                sock.settimeout(min(left, ATTEMPT_SECONDS))
                if source_address:
                    sock.bind(source_address)
                sock.connect(where)
                return sock
            except OSError as error:
                last = error
                sock.close()
        raise TimeoutError(
            f"no address for {host} accepted a connection within {budget:g}s"
        ) from last

    return connect


def _by_turns(infos: list) -> list:
    """The same addresses, alternating between IPv6 and IPv4.

    A resolver lists one family first. If its route is a black hole, trying
    them in order spends every attempt on it. curl races the families; taking
    turns is the cheap half, and enough to stop a run hanging.
    """
    families: dict[int, list] = {}
    for info in infos:
        families.setdefault(info[0], []).append(info)
    taking = list(families.values())
    return [info for group in zip_longest(*taking) for info in group if info]


def _detail(error: urllib.error.HTTPError) -> str:
    try:
        return error.read().decode()[:400]
    except Exception:
        return str(error)
