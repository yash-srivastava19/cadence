from typing import NamedTuple

from cadence.exceptions import CadenceError

__all__ = ["BEGIN", "END", "Region", "split", "splice", "MarkerError"]

BEGIN = "CADENCE:BEGIN"
END = "CADENCE:END"


class MarkerError(CadenceError):
    pass


class Region(NamedTuple):
    head: str
    body: str
    tail: str


def split(code: str) -> Region | None:
    lines = code.splitlines(keepends=True)
    opens = [i for i, line in enumerate(lines) if BEGIN in line]
    closes = [i for i, line in enumerate(lines) if END in line]
    if not opens and not closes:
        return None
    if len(opens) != 1 or len(closes) != 1:
        raise MarkerError(
            f"a program needs exactly one {BEGIN} and one {END};"
            f" found {len(opens)} and {len(closes)}"
        )
    start, stop = opens[0], closes[0]
    if stop <= start:
        raise MarkerError(f"{END} comes before {BEGIN}")
    return Region(
        head="".join(lines[: start + 1]),
        body="".join(lines[start + 1 : stop]),
        tail="".join(lines[stop:]),
    )


def splice(code: str, body: str) -> str:
    region = split(code)
    if region is None:
        raise MarkerError(f"the program has no {BEGIN} marker")
    if not body.endswith("\n"):
        body += "\n"
    return region.head + body + region.tail
