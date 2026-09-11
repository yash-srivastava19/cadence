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

from cadence.web.api import Answer, answer

__all__ = ["serve"]

#: Localhost, spelled out. "" would bind every interface, which on a laptop
#: on a shared network publishes someone's source code to it.
HOST = "127.0.0.1"


def serve(open_session: Callable, port: int = 8787, host: str = HOST) -> None:
    """Serve until interrupted. Blocks."""
    server = ThreadingHTTPServer((host, port), _handler(open_session))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _handler(open_session: Callable) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        # Only GET is defined, so every other verb gets a 501 from the base
        # class. That is the read-only promise enforced rather than stated.
        def do_GET(self) -> None:  # the name is the base class's, not ours
            parsed = urlparse(self.path)
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                said = answer(parsed.path, params, open_session)
            except Exception as error:
                # A 500 should never happen, and when it does the person
                # looking at it is the person who can fix it: say what broke
                # rather than dropping the connection on them.
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
