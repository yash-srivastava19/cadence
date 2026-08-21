import random

from cadence.interfaces import Objective, Task
from cadence.objectives import Pareto, WeightedSum

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


class TestATaskIsUsable:
    def test_a_plain_class_satisfies_the_protocol(self):
        assert isinstance(Knapsack(), Task)

    def test_the_same_seed_gives_the_same_inputs(self):
        task = Knapsack()
        assert task.inputs(7) == task.inputs(7)

    def test_different_seeds_give_different_inputs(self):
        task = Knapsack()
        assert task.inputs(1) != task.inputs(2)

    def test_scoring_a_real_solution_returns_metrics(self):
        task = Knapsack()
        inputs = task.inputs(7)
        metrics = task.score(greedy(*inputs), inputs)
        assert metrics["value"] > 0
        assert metrics["weight"] <= CAPACITY

    def test_the_baseline_runs_and_scores(self):
        task = Knapsack()
        namespace = {}
        exec(task.baseline, namespace)
        inputs = task.inputs(7)
        metrics = task.score(namespace[task.entry_point](*inputs), inputs)
        assert metrics == {"value": 0.0, "weight": 0.0}

    def test_an_overweight_answer_scores_nothing(self):
        task = Knapsack()
        inputs = task.inputs(7)
        everything = list(range(len(inputs[0])))
        assert task.score(everything, inputs)["value"] == 0.0


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
