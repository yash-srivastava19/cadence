"""The winner is whatever the search method ranks first.

What every run did before pick was a port of its own, kept as the default
so that a manifest without `pick:` reports the same winner it always did.
"""

from cadence.core.dto import Picked, RunHistory
from cadence.core.ports import Measure, Method, Objective

__all__ = ["Best"]


class Best:
    def __init__(self, method: Method, objective: Objective | None = None) -> None:
        self.method = method

    def pick(self, history: RunHistory, measure: Measure) -> Picked | None:
        best = self.method.best(history)
        return Picked(result=best) if best is not None else None
