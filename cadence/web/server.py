"""A socket in front of `answer`.

`http.server` rather than a framework. It is in the standard library, this
is a read-only local dashboard serving one person, and a first web dependency
is a thing every future contributor has to install to run the tests. If it
ever needs to serve more than the laptop it runs on, that is the moment to
bring in something that was designed to.

Bound to localhost and nothing else: there is no authentication here, and
every run's manifest and every candidate's source is readable through it.
"""

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from cadence.errors import SetupError
from cadence.web.api import Answer, answer

__all__ = ["serve"]

HOST = "127.0.0.1"


def serve(
    open_session: Callable,
    port: int = 8787,
    host: str = HOST,
    ready: Callable[[], None] | None = None,
) -> None:
    """Serve until interrupted. Blocks.

    `ready` is called once the socket is actually listening, because the
    caller's job is to print a URL and a URL printed before the bind is a
    URL that may never work -- which is exactly what happened the first time
    this met a port somebody was already using.
    """
    try:
        server = ThreadingHTTPServer((host, port), _handler(open_session))
    except OSError as error:
        raise SetupError(
            f"cannot serve on {host}:{port} -- {error.strerror}"
        ) from error
    if ready is not None:
        ready()
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _handler(open_session: Callable) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # the name is the base class's, not ours
            parsed = urlparse(self.path)
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                said = answer(parsed.path, params, open_session)
            except Exception as error:
                said = _broke(error)
            self._send(said)

        def _send(self, said: Answer) -> None:
            body = said.body.encode()
            self.send_response(said.status)
            self.send_header("Content-Type", said.content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:
            """Quiet. The terminal running this is the one the user is
            watching their run's output in."""

    return Handler


def _broke(error: Exception) -> Answer:
    return Answer(500, json.dumps({"error": f"{type(error).__name__}: {error}"}))
