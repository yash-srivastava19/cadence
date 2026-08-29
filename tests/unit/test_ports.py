import random

from cadence.control.objectives.ranking import Pareto, WeightedSum
from cadence.core.ports import Objective

CAPACITY = 20


class Knapsack:
    entry_point = "pack"

    baseline = """
def pack(items, capacity):
    return []
"""

    def inputs(self, seed):
        rng = random.Random(seed)
        return [(rng.randint(1, 10), rng.randint(1, 10)) for _ in range(8)], CAPACITY

    def score(self, output, inputs):
        items, capacity = inputs
        chosen = [items[i] for i in output]
        weight = sum(w for w, _ in chosen)
        value = sum(v for _, v in chosen)
        return {
            "value": float(value) if weight <= capacity else 0.0,
            "weight": float(weight),
        }


def greedy(items, capacity):
    order = sorted(range(len(items)), key=lambda i: -items[i][1] / items[i][0])
    picked, weight = [], 0
    for i in order:
        if weight + items[i][0] <= capacity:
            picked.append(i)
            weight += items[i][0]
    return picked


class TestAnObjectiveRanksThoseMetrics:
    def test_a_solution_beats_the_baseline(self):
        task = Knapsack()
        inputs = task.inputs(7)
        objective = WeightedSum(value=1.0)
        solved = task.score(greedy(*inputs), inputs)
        nothing = task.score([], inputs)
        assert objective.dominates(solved, nothing)

    def test_both_objectives_satisfy_the_protocol(self):
        assert isinstance(WeightedSum(value=1.0), Objective)
        assert isinstance(Pareto(value=1), Objective)

    def test_the_two_objectives_disagree_on_a_trade_off(self):
        cheap = {"value": 5.0, "weight": 1.0}
        rich = {"value": 10.0, "weight": 9.0}
        assert WeightedSum(value=1.0, weight=-0.2).dominates(rich, cheap)
        assert not Pareto(value=1, weight=-1).dominates(rich, cheap)
