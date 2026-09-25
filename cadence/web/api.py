"""Which URL means which query.

The whole of the web plane's thinking, and there is deliberately very little
of it: a path picks a query, the query returns DTOs, and `as_json` turns them
into the same bytes `cadence runs list --json` prints. One serializer, two
ways to reach it.

A function of (path, params) rather than a framework, so that every route can
be tested without a socket.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import unquote

from sqlalchemy.orm import Session

from cadence.control.queries import (
    PAGE,
    run_detail,
    some_experiments,
    some_runs,
    some_trials,
    trial_detail,
)
from cadence.delivery import as_json
from cadence.web.page import VENDOR, page, version

__all__ = ["Answer", "answer"]

JSON = "application/json"
HTML = "text/html; charset=utf-8"

VENDORED = {
    "diff2html.min.js": "text/javascript; charset=utf-8",
    "diff2html.min.css": "text/css; charset=utf-8",
}


@dataclass(frozen=True)
class Answer:
    """What to send back. A value, so the server does no thinking either."""

    status: int
    body: str
    content_type: str = JSON


def answer(path: str, params: Mapping[str, str], open_session: Callable) -> Answer:
    """Route one request.

    `open_session` is passed in rather than reached for: the CLI already has
    a session context manager with the door checks on it, and a second way of
    opening a database would be a second place for them to drift apart.
    """
    if path in ("/", "/index.html"):
        return Answer(200, page(), HTML)
    if path == "/api/version":
        return Answer(200, json.dumps({"page": version()}))
    if path.startswith("/vendor/"):
        return _vendored(path[len("/vendor/") :])
    if not path.startswith("/api/"):
        return _missing(path)
    rest = [unquote(part) for part in path[len("/api/") :].strip("/").split("/")]
    with open_session() as session:
        return _dispatch(rest, params, session)


def _vendored(name: str) -> Answer:
    if name not in VENDORED:
        return _missing("/vendor/" + name)
    return Answer(200, (VENDOR / name).read_text(encoding="utf-8"), VENDORED[name])


def _dispatch(rest: list[str], params: Mapping[str, str], session: Session) -> Answer:
    match rest:
        case ["experiments"]:
            return _found(some_experiments(session, _limit(params)))
        case ["runs"]:
            return _found(
                some_runs(
                    session,
                    params.get("experiment"),
                    params.get("owner"),
                    params.get("status"),
                    _limit(params),
                )
            )
        case ["runs", run_id]:
            return _one(run_detail(session, run_id), "run", run_id)
        case ["runs", run_id, "trials"]:
            return _found(
                some_trials(session, run_id, params.get("status"), _limit(params))
            )
        case ["trials", trial_id]:
            return _one(trial_detail(session, trial_id), "trial", trial_id)
    return _missing("/api/" + "/".join(rest))


def _limit(params: Mapping[str, str]) -> int:
    """A limit the caller can raise, and cannot use to ask for everything.

    The query string is the one input here nobody in this repo wrote, so it
    is the one that has to be wrong-proof: a missing limit, a word, or a
    number with six digits in it all have to come out as a number of rows
    somebody is willing to wait for.
    """
    try:
        asked = int(params.get("limit", PAGE))
    except ValueError:
        return PAGE
    return max(1, min(asked, 500))


def _found(rows) -> Answer:
    return Answer(200, as_json(rows))


def _one(row, kind: str, named: str) -> Answer:
    if row is None:
        return Answer(404, as_json_error(f"no {kind} called {named!r}"))
    return Answer(200, as_json(row))


def _missing(path: str) -> Answer:
    return Answer(404, as_json_error(f"nothing at {path!r}"))


def as_json_error(said: str) -> str:
    """The one string this plane builds itself.

    Rule 4 says one plane knows how output looks and this is it -- but an
    error shaped by hand here, rather than a Value passed to `as_json`, is a
    small crack. If a third kind of failure ever needs saying, it becomes a
    DTO.
    """
    return json.dumps({"error": said}, indent=2)
