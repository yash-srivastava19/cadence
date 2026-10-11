"""Every candidate is measured once, on every one of the run's seeds.

What every trial did before judging was a port of its own, kept as the
default so that a manifest without `judge:` measures as it always did.
"""

from cadence.core.dto import Measurement, RunHistory
from cadence.core.ports import Measure, Objective

__all__ = ["Full"]


class Full:
    def __init__(self, objective: Objective | None = None) -> None:
        pass

    def judge(self, code: str, history: RunHistory, measure: Measure) -> Measurement:
        return measure(code)
