"""A result, for whatever comes next.

The same value the text presenters are given. That is the point of having
two: `cadence run --json | jq '.spend.tokens'` and the two-column output are
the same facts, and neither is the one the loop knows about.
"""

import json
from collections.abc import Sequence

from cadence.core.values import Value

__all__ = ["as_json"]


def as_json(what: Value | Sequence[Value]) -> str:
    if isinstance(what, Value):
        return json.dumps(what.model_dump(mode="json"), indent=2, sort_keys=True)
    return json.dumps(
        [one.model_dump(mode="json") for one in what], indent=2, sort_keys=True
    )
