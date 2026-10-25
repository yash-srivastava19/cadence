"""A hosted sandbox: one POST in, one measurement out, in a fresh container.

    POST /run   Authorization: Bearer <token>   body: a `cadence sandbox` request

The body is piped into `docker run -i cadence-sandbox`, which is
`cadence sandbox` in a container with no network, and whatever it prints is
the answer. Tokens are one per line in the file named by CADENCE_TOKENS.

Bound to localhost; something in front (Tailscale Funnel, a load balancer)
terminates TLS. Stdlib only, so the box needs Python and Docker and nothing
from pip.
"""

import hmac
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IMAGE = os.environ.get("CADENCE_SANDBOX_IMAGE", "cadence-sandbox")
TOKENS = Path(os.environ.get("CADENCE_TOKENS", "/etc/cadence/tokens"))
LARGEST_REQUEST = 64 * 1024 * 1024
#: Container start and unpacking, on top of the job's own limit.
OVERHEAD_SECONDS = 120


def allowed(header: str | None) -> bool:
    if not header or not header.startswith("Bearer "):
        return False
    given = header.removeprefix("Bearer ").strip().encode()
    known = [line.strip().encode() for line in TOKENS.read_text().splitlines()]
    return any(hmac.compare_digest(given, token) for token in known if token)


def measure(request: bytes) -> subprocess.CompletedProcess:
    job = json.loads(request)["job"]
    memory = int(job["memory_mb"]) + 256
    return subprocess.run(
        [
            "docker",
            "run",
            "-i",
            "--rm",
            "--network",
            "none",
            "--memory",
            f"{memory}m",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            IMAGE,
        ],
        input=request,
        capture_output=True,
        timeout=float(job["seconds"]) + OVERHEAD_SECONDS,
    )


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/run":
            return self._reply(404, b"no such route\n")
        if not allowed(self.headers.get("Authorization")):
            return self._reply(401, b"unknown token\n")
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= LARGEST_REQUEST:
            return self._reply(413, b"request missing or too large\n")
        try:
            done = measure(self.rfile.read(length))
        except subprocess.TimeoutExpired:
            return self._reply(504, b"the container did not finish in time\n")
        except (ValueError, KeyError) as error:
            return self._reply(400, f"not a sandbox request: {error}\n".encode())
        if done.returncode != 0:
            return self._reply(502, done.stderr[-2000:] or b"the container failed\n")
        self._reply(200, done.stdout)

    def _reply(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
