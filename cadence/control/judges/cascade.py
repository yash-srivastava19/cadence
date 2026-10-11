"""Measure cheaply first, and fully only what might be worth it.

Most candidates are worse than what the run already has, and a full
measurement of each one is most of what a slow scorer costs. This scores a
candidate on a few seeds first and goes on to the run's seeds only when that
quick score is at least as good as a given share of what the run has scored.

A candidate that stops early keeps its quick score as its verdict, measured
on fewer seeds than the rest. That is the trade: it is cheaper, and it is
noisier, so it suits scores that a few seeds already rank well.
"""

from collections.abc import Sequence

from cadence.core.dto import Measurement, RunHistory
from cadence.core.ports import Measure, Objective
from cadence.core.verdict import Scored

__all__ = ["Cascade"]


class Cascade:
    def __init__(
        self, objective: Objective, seeds: Sequence[int], above: float = 0.5
    ) -> None:
        if not seeds:
            raise ValueError("the first stage needs at least one seed")
        if not 0 <= above <= 1:
            raise ValueError("above is a share of scored programs, from 0 to 1")
        self.objective = objective
        self.seeds = tuple(seeds)
        self.above = above

    def judge(self, code: str, history: RunHistory, measure: Measure) -> Measurement:
        quick = measure(code, self.seeds)
        if not isinstance(quick.verdict, Scored):
            return quick
        scored = [r.metrics for r in history.scored if r.metrics is not None]
        if not scored:
            return measure(code)
        quick_score = quick.verdict.metrics
        # "At least as good as" rather than "better than": under a Pareto
        # objective most pairs are incomparable, and incomparable is not worse.
        matched = sum(
            1 for other in scored if not self.objective.dominates(other, quick_score)
        )
        if matched / len(scored) >= self.above:
            return measure(code)
        return quick
