"""Run Cadence against this directory with a fake model.

    cd examples/lab && python demo.py

Same thing `cadence run` does, but with scripted answers instead of an API key.
"""

import difflib
from pathlib import Path

from cadence.backends import Scripted
from cadence.manifest import load
from cadence.registry import build
from cadence.signals import PatchRejected, TrialAbandoned, TrialMeasured, cadence

GREEDY = """    order = sorted(range(len(items)), key=lambda i: -items[i][1] / items[i][0])
    chosen, used = [], 0
    for index in order:
        if used + items[index][0] <= capacity:
            chosen.append(index)
            used += items[index][0]
    return chosen"""


def as_diff(before: str, after: str) -> str:
    body = difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), "a/pack.py", "b/pack.py"
    )
    return f"```diff\n{''.join(body)}```"


def watch(fact):
    if isinstance(fact, TrialMeasured) and fact.verdict.is_scored:
        print(f"    scored   value {fact.verdict.metrics['value']:.0f}")
    elif isinstance(fact, TrialMeasured):
        print(
            f"    {fact.verdict.outcome}  {fact.verdict.reason.splitlines()[-1][:50]}"
        )
    elif isinstance(fact, (PatchRejected, TrialAbandoned)):
        print(f"    rejected {fact.reason[:50]}")


def main() -> None:
    root = Path(__file__).parent
    manifest = load(root)
    start = (root / manifest.program).read_text()

    print(f"starting from {manifest.program}:\n")
    print("    " + start.split("def pack")[1].strip()[:60])

    answers = [as_diff(start, start.replace("    return []", GREEDY)), "I'd use DP."]
    experiment = build(manifest, root, "demo", backend=Scripted(*answers))

    print(f"\nrunning {manifest.budget.trials} trials against a fake model:\n")
    stop = cadence.subscribe(watch)
    report = experiment.run()
    stop()

    print(f"\n{report.status}: value {report.metrics['value']:.0f}\n")
    print(report.program)


if __name__ == "__main__":
    main()
