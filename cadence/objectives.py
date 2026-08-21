from collections.abc import Mapping

from cadence.interfaces import Metrics

__all__ = ["WeightedSum", "Pareto", "MissingMetric"]


class MissingMetric(KeyError):
    pass


def _read(metrics: Metrics, names: Mapping[str, float]) -> list[float]:
    missing = sorted(set(names) - set(metrics))
    if missing:
        raise MissingMetric(f"verdict has no {', '.join(missing)}")
    return [metrics[name] for name in names]


class WeightedSum:
    def __init__(self, **weights: float) -> None:
        if not weights:
            raise ValueError("a weighted sum needs at least one weight")
        self.weights = weights

    def total(self, metrics: Metrics) -> float:
        values = _read(metrics, self.weights)
        return sum(
            weight * value for weight, value in zip(self.weights.values(), values)
        )

    def dominates(self, a: Metrics, b: Metrics) -> bool:
        return self.total(a) > self.total(b)


class Pareto:
    def __init__(self, **senses: float) -> None:
        if not senses:
            raise ValueError("a pareto front needs at least one metric")
        if any(sense == 0 for sense in senses.values()):
            raise ValueError("a sense of 0 gives a metric no direction")
        self.senses = senses

    def _oriented(self, metrics: Metrics) -> list[float]:
        values = _read(metrics, self.senses)
        return [sense * value for sense, value in zip(self.senses.values(), values)]

    def dominates(self, a: Metrics, b: Metrics) -> bool:
        mine, theirs = self._oriented(a), self._oriented(b)
        return all(x >= y for x, y in zip(mine, theirs)) and mine != theirs
