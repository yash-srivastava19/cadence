import re
from collections.abc import Sequence

import whatthepatch
from whatthepatch.exceptions import WhatThePatchException

from cadence.exceptions import PatchError

__all__ = ["apply_patch", "recount"]

HUNK = re.compile(r"^@@\s*-\d+(?:,\d+)?\s*\+\d+(?:,\d+)?\s*@@")


def apply_patch(code: str, patch: Sequence[str]) -> str:
    try:
        return _apply(code, patch)
    except PatchError:
        return _apply(code, recount(code, patch))


def recount(code: str, patch: Sequence[str]) -> list[str]:
    lines = list(code.splitlines())
    out: list[str] = []
    for header, body in _hunks(patch):
        if header is None:
            out.extend(body)
            continue
        before = [line[1:] for line in body if line[:1] in (" ", "-")]
        after = [line[1:] for line in body if line[:1] in (" ", "+")]
        start = _find(lines, before)
        out.append(f"@@ -{start + 1},{len(before)} +{start + 1},{len(after)} @@")
        out.extend(body)
    return out


def _hunks(patch: Sequence[str]) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in patch:
        if HUNK.match(line):
            sections.append((line, []))
        else:
            sections[-1][1].append(line)
    return sections


def _find(lines: list[str], wanted: list[str]) -> int:
    if not wanted:
        return 0
    width = len(wanted)
    for start in range(len(lines) - width + 1):
        if lines[start : start + width] == wanted:
            return start
    stripped = [line.strip() for line in wanted]
    for start in range(len(lines) - width + 1):
        if [line.strip() for line in lines[start : start + width]] == stripped:
            return start
    raise PatchError(f"no lines in the program match {wanted[0].strip()!r}")


def _apply(code: str, patch: Sequence[str]) -> str:
    text = "\n".join(patch) + "\n"
    diffs = [diff for diff in whatthepatch.parse_patch(text) if diff.changes]
    if not diffs:
        raise PatchError("the patch has no hunks")
    for diff in diffs:
        try:
            code = "\n".join(whatthepatch.apply_diff(diff, code))
        except WhatThePatchException as error:
            raise PatchError(str(error)) from error
    return code
