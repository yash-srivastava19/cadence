"""Two ways to say which of two sets of metrics is better.

Both do the same two things first -- look up the metrics they were named, and
turn them the right way round -- and differ only in what they do with the
result. That shared half is the base; each dominates() is three lines.
"""

from cadence.core.types import Metrics
from cadence.errors import MissingMetric

__all__ = ["Pareto", "WeightedSum"]


class Weighted:
    """Metrics scaled by a number per metric. What the number means is the
    subclass's business: a weight to sum, or a direction to compare along."""

    def __init__(self, needs: str, **weights: float) -> None:
        if not weights:
            raise ValueError(needs)
        self.weights = weights

    def oriented(self, metrics: Metrics) -> list[float]:
        missing = sorted(set(self.weights) - set(metrics))
        if missing:
            raise MissingMetric(f"verdict has no {', '.join(missing)}")
        return [weight * metrics[name] for name, weight in self.weights.items()]


class WeightedSum(Weighted):
    """One number: everything added up. Cannot express a trade-off."""

    def __init__(self, **weights: float) -> None:
        super().__init__("a weighted sum needs at least one weight", **weights)

    def total(self, metrics: Metrics) -> float:
        return sum(self.oriented(metrics))

    def dominates(self, a: Metrics, b: Metrics) -> bool:
        return self.total(a) > self.total(b)


class Pareto(Weighted):
    """Better at everything and worse at nothing. Leaves trade-offs
    incomparable, which is the entire reason dominates() is not compare()."""

    def __init__(self, **senses: float) -> None:
        super().__init__("a pareto front needs at least one metric", **senses)
        if any(sense == 0 for sense in senses.values()):
            raise ValueError("a sense of 0 gives a metric no direction")

    def dominates(self, a: Metrics, b: Metrics) -> bool:
        mine, theirs = self.oriented(a), self.oriented(b)
        return all(x >= y for x, y in zip(mine, theirs, strict=True)) and mine != theirs
