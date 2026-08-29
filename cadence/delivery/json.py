"""A finished run, for whatever comes next.

The same Report the text presenter is given. That is the point of having two:
`cadence run --json | jq '.spend.tokens'` and the two-column output are the
same facts, and neither is the one the loop knows about.
"""

import json

from cadence.core.dto import Report

__all__ = ["as_json"]


def as_json(report: Report) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)
