"""Cadence improves a program you already wrote.

    python examples/quickstart.py

Runs against a fake model, so it needs no API key, no network and no database.
"""

import textwrap

from cadence.backends import Scripted
from cadence.experiment import Experiment
from cadence.methods import Evolution
from cadence.model import Model
from cadence.objectives import WeightedSum
from cadence.runner import TrialRunner
from cadence.sandbox import Subprocess
from cadence.signals import PatchRejected, TrialAbandoned, TrialMeasured, cadence

CAPACITY = 20
ITEMS = [(3, 8), (7, 14), (4, 9), (9, 15), (2, 5), (5, 11), (6, 12), (8, 13)]

# ---------------------------------------------------------------- your part

START = '''\
def pack(items, capacity):
    """Pick indexes of (weight, value) items worth the most, without going over capacity."""
    return []
'''


class Knapsack:
    """The problem. Three things Cadence needs from you, and nothing else."""

    entry_point = "pack"
    baseline = START

    def inputs(self, seed):
        return ITEMS, CAPACITY

    def score(self, chosen, inputs):
        items, capacity = inputs
        weight = sum(items[i][0] for i in chosen)
        value = sum(items[i][1] for i in chosen)
        return {"value": float(value) if weight <= capacity else 0.0}


# ------------------------------------------------- what a model would send

GREEDY = '''\
def pack(items, capacity):
    """Pick indexes of (weight, value) items worth the most, without going over capacity."""
    chosen, used = [], 0
    for index, (weight, value) in enumerate(items):
        if used + weight <= capacity:
            chosen.append(index)
            used += weight
    return chosen
'''

BY_RATIO = '''\
def pack(items, capacity):
    """Pick indexes of (weight, value) items worth the most, without going over capacity."""
    order = sorted(range(len(items)), key=lambda i: -items[i][1] / items[i][0])
    chosen, used = [], 0
    for index in order:
        weight = items[index][0]
        if used + weight <= capacity:
            chosen.append(index)
            used += weight
    return chosen
'''


def rewrite(before, after):
    """The diff a model would reply with, rewriting the whole function."""
    old = before.splitlines()
    new = after.splitlines()
    body = [f"-{line}" for line in old] + [f"+{line}" for line in new]
    return "\n".join(
        [
            "```diff",
            "--- a/pack.py",
            "+++ b/pack.py",
            f"@@ -1,{len(old)} +1,{len(new)} @@",
            *body,
            "```",
        ]
    )


REPLIES = [
    rewrite(START, GREEDY),
    "Honestly I would just use dynamic programming here.",
    rewrite(GREEDY, BY_RATIO),
]

# ------------------------------------------------------------------ output


def show(code, indent="      "):
    print(textwrap.indent(code.rstrip(), indent))


def rule(title):
    print(f"\n{'-' * 62}\n{title}\n")


def main():
    print(__doc__.splitlines()[0])

    rule("WHAT YOU PROVIDE")
    print("      1. a program to start from")
    print("      2. inputs to run it on")
    print("      3. a way to score the answer\n")
    print("      Everything after that is Cadence.")

    rule("THE PROBLEM")
    print(f"      Pack a knapsack. Capacity {CAPACITY}, {len(ITEMS)} items of")
    print("      (weight, value). Higher packed value is better.")

    rule("THE PROGRAM YOU START WITH")
    show(START)
    task = Knapsack()
    start_value = task.score([], task.inputs(0))["value"]
    print(f"\n      It packs nothing, so it scores {start_value:.0f}.")

    rule(f"RUNNING {len(REPLIES)} TRIALS   (fake model, no API key)")

    so_far = {"n": 0, "best": start_value}

    def report_trial(fact):
        if not isinstance(fact, (TrialMeasured, PatchRejected, TrialAbandoned)):
            return
        so_far["n"] += 1
        label = f"      trial {so_far['n']}   "
        if isinstance(fact, (PatchRejected, TrialAbandoned)):
            print(f"{label}patch rejected    {fact.reason[:44]}")
        elif isinstance(fact, TrialMeasured) and fact.verdict.is_scored:
            got = fact.verdict.metrics["value"]
            print(f"{label}patch applied     value {so_far['best']:.0f} -> {got:.0f}")
            so_far["best"] = max(so_far["best"], got)
        elif isinstance(fact, TrialMeasured):
            print(f"{label}{fact.verdict.outcome}          {fact.verdict.reason[:40]}")

    stop = cadence.subscribe(report_trial)

    experiment = Experiment(
        run_id="quickstart",
        method=Evolution(objective=WeightedSum(value=1.0), size=1),
        model=Model(backend=Scripted(*REPLIES)),
        runner=TrialRunner(task=task, sandbox=Subprocess(), seeds=(0,)),
        seeds=[START],
        budget=len(REPLIES),
    )
    result = experiment.run()
    stop()

    rule("RESULT")
    if result.metrics:
        print(f"      value {result.metrics['value']:.0f}, up from {start_value:.0f}\n")
    if result.program:
        show(result.program)

    rule("WHAT TO CHANGE")
    print("      Swap Knapsack for your own problem: a program, some inputs,")
    print("      and a score. Swap Scripted for a real model when you have")
    print("      a key. Nothing else in this file has to move.")


if __name__ == "__main__":
    main()
