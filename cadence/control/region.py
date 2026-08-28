from typing import NamedTuple

from cadence.errors import SetupError

__all__ = ["BEGIN", "END", "MarkerError", "Region", "splice", "split"]

BEGIN = "CADENCE:BEGIN"
END = "CADENCE:END"


class MarkerError(SetupError):
    pass


class Region(NamedTuple):
    head: str
    body: str
    tail: str


def split(code: str, begin: str = BEGIN, end: str = END) -> Region | None:
    lines = code.splitlines(keepends=True)
    opens = [i for i, line in enumerate(lines) if begin in line]
    closes = [i for i, line in enumerate(lines) if end in line]
    if not opens and not closes:
        return None
    if len(opens) != 1 or len(closes) != 1:
        raise MarkerError(
            f"a program needs exactly one {begin} and one {end};"
            f" found {len(opens)} and {len(closes)}"
        )
    start, stop = opens[0], closes[0]
    if stop <= start:
        raise MarkerError(f"{end} comes before {begin}")
    return Region(
        head="".join(lines[: start + 1]),
        body="".join(lines[start + 1 : stop]),
        tail="".join(lines[stop:]),
    )


def splice(code: str, body: str, begin: str = BEGIN, end: str = END) -> str:
    region = split(code, begin, end)
    if region is None:
        raise MarkerError(f"the program has no {begin} marker")
    if not body.endswith("\n"):
        body += "\n"
    return region.head + body + region.tail
