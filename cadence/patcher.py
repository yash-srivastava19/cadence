from collections.abc import Sequence

import whatthepatch
from whatthepatch.exceptions import WhatThePatchException

from cadence.exceptions import PatchError

__all__ = ["apply_patch"]


def apply_patch(code: str, patch: Sequence[str]) -> str:
    diffs = [
        diff
        for diff in whatthepatch.parse_patch("\n".join(patch) + "\n")
        if diff.changes
    ]
    if not diffs:
        raise PatchError("the patch has no hunks")
    for diff in diffs:
        try:
            code = "\n".join(whatthepatch.apply_diff(diff, code))
        except WhatThePatchException as error:
            raise PatchError(str(error)) from error
    return code
