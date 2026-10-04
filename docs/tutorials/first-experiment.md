# Run your first experiment

This tutorial builds a small, complete Cadence project. The goal is not to find a novel algorithm. The goal is to learn the shape of a trustworthy experiment: a marked program, a scorer outside the region, a baseline, and a preflight check.

## What you will build

The program chooses a number from a list. The scorer rewards a choice close to the largest value. It is intentionally small so you can inspect every part of the run.

## 1. Create the project

```bash
mkdir cadence-first-experiment
cd cadence-first-experiment
cadence init
```

Replace the generated `solve.py` with:

```python title="solve.py"
def solve(values: list[int]) -> int:
    # CADENCE:BEGIN
    return values[0]
    # CADENCE:END
```

The markers define the only region Cadence may rewrite. Keep the function signature outside the region when possible; it gives every candidate the same interface.

## 2. Write the scorer

Replace `score.py` with:

```python title="score.py"
import json
import random

from solve import solve


def main() -> None:
    seed = int(__import__("os").environ.get("CADENCE_SEED", "0"))
    random.seed(seed)
    values = [random.randrange(100) for _ in range(20)]
    result = solve(values)
    target = max(values)
    print(json.dumps({"score": -abs(target - result)}))


if __name__ == "__main__":
    main()
```

The scorer owns the test data and the objective. A higher score is better because the distance is negated.

## 3. Configure the manifest

Use this small budget while learning:

```yaml title=".cadence"
api_version: cadence/v1alpha2
program: solve.py
run: python score.py
metrics:
  score: maximize
budget:
  trials: 3
model:
  scripted: {}
sandbox:
  seconds: 10
  memory_mb: 256
  seeds: [0, 1, 2]
```

The scripted provider is useful for tests and demonstrations. For a real search, choose a hosted or local provider as described in [Get started](../get-started/index.md).

## 4. Check the harness

```bash
cadence check
```

Read the output as a contract. It should identify the region, scorer, baseline metric, seeds, sandbox, and trial budget. It should not call a model.

If the baseline fails, fix the scorer first. A model call cannot make a broken measurement useful.

## 5. Run and inspect

```bash
cadence run
```

The result is a report containing the best candidate and its verdict. The local JSONL log under `cadence-runs/` contains the steps that led there.

With a database configured, use:

```bash
cadence runs list
cadence runs show RUN_ID
cadence trials list --run RUN_ID
```

## 6. What you learned

- Cadence changes only the marked region.
- The scorer stays outside that region.
- `check` is a measurement preflight, not a dry-run prompt.
- A candidate result is a verdict with evidence or a reason for failure.
- A run can be inspected without reading the database directly.

## Next

- [Bring your own program](../guides/bring-your-own-program.md)
- [Design a scorer](../guides/design-a-scorer.md)
- [Understand resumability](../concepts/resumability.md)
