# Tasks

A `Task` is how you point Cadence at your own problem. It is the only thing
you have to write, and it is four members long.

This page is the canonical reference. If another page shows a shorter version,
this one is right.

## The interface

```python
from src.task import Task
from src.models import EvaluationResult
```

| Member | Kind | Returns | Does |
| --- | --- | --- | --- |
| `function_name` | property | `str` | Names the function Cadence pulls out of the evolved code |
| `generate_inputs` | method | anything | Builds one problem instance from a seed, deterministically |
| `evaluate` | method | `EvaluationResult` | Scores one output. Lower cost is better |
| `baseline_program` | property | `str` | The starting program, with evolution markers |

Two more are optional and default to permissive:

| Member | Default | Override when |
| --- | --- | --- |
| `task_type` | `TaskType.CUSTOM` | You want the type recorded in the database |
| `is_feasible` | always `True` | Feasibility is cheaper to check separately from scoring |

## A complete example

A knapsack task, start to finish. Nothing is elided.

```python
import random
from typing import Any, Dict, List

from src.task import Task
from src.models import EvaluationResult


class KnapsackTask(Task):
    """Pack the most value into a fixed-capacity bag."""

    def __init__(self, n_items: int = 20) -> None:
        self.n_items = n_items

    @property
    def function_name(self) -> str:
        return "knapsack"

    def generate_inputs(self, seed: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        items = [
            {"weight": rng.randint(1, 30), "value": rng.randint(1, 100)}
            for _ in range(self.n_items)
        ]
        return {"items": items, "capacity": 100}

    def evaluate(self, output: Any, input_data: Any) -> EvaluationResult:
        items = input_data["items"]
        capacity = input_data["capacity"]

        if not isinstance(output, list):
            return EvaluationResult(
                cost=1e8, feasible=False, error=f"expected a list, got {type(output)}"
            )
        if any(not isinstance(i, int) or not 0 <= i < len(items) for i in output):
            return EvaluationResult(
                cost=1e8, feasible=False, error="index out of range"
            )
        if len(set(output)) != len(output):
            return EvaluationResult(
                cost=1e8, feasible=False, error="an item was packed twice"
            )

        weight = sum(items[i]["weight"] for i in output)
        if weight > capacity:
            return EvaluationResult(
                cost=1e8,
                feasible=False,
                error=f"over capacity: {weight} > {capacity}",
            )

        value = sum(items[i]["value"] for i in output)
        # Cadence minimises, so return negated value shifted positive.
        total = sum(i["value"] for i in items)
        return EvaluationResult(cost=float(total - value), feasible=True)

    @property
    def baseline_program(self) -> str:
        return '''### START_BLOCK
def knapsack(input_data):
    """Greedy by value. Deliberately mediocre — evolution has room to work."""
    items = input_data["items"]
    capacity = input_data["capacity"]
    order = sorted(range(len(items)), key=lambda i: -items[i]["value"])
    chosen, used = [], 0
    for i in order:
        if used + items[i]["weight"] <= capacity:
            chosen.append(i)
            used += items[i]["weight"]
    return chosen
### END_BLOCK'''
```

Run it:

```python
from src.evaluator import execute

task = KnapsackTask(n_items=20)
print(execute(task.baseline_program, task))
```

That prints `{'cost': ..., 'feasibility': 1.0}`. A feasibility below `1.0`
means some seeds failed, and is the first thing to check.

## The four rules

### 1. Lower cost is better, always

`EvaluationResult.cost` is minimised. A maximisation problem must be negated
or subtracted from a constant, as the knapsack example does. Cost must also be
non-negative — the model validator rejects negatives.

For a failure, return `cost=1e8` (`INFEASIBLE_COST` in `src/evaluator.py`) and
`feasible=False`. Anything non-finite is normalised to that value anyway.

### 2. `generate_inputs` must be deterministic

The same seed must produce the same instance forever, or scores from
different generations are not comparable and the search is measuring noise.

Use `random.Random(seed)`, not `random.seed(seed)`. The module-level version
mutates global state that your evolved program also uses.

### 3. Always fill in `error`

```python
EvaluationResult(cost=1e8, feasible=False, error="tour revisits city 3")
```

The string costs nothing and is the difference between a debuggable run and a
column of `1e8`.

Be aware of a current limitation: `execute()` collects these strings per seed
and then drops them when aggregating, so they do not reach the next prompt.
They do reach you, through `evaluate_on_task()`, when you call it directly.

### 4. Mark exactly what may change

```text
### START_BLOCK
def knapsack(input_data):
    ...
### END_BLOCK
```

Everything between the markers is what the model rewrites. Everything outside
is fixed, and the prompt tells the model so.

Keep imports and helper functions **outside** the markers if the model must not
touch them — but remember that the whole file is executed, so anything the
evolved function needs must be somewhere in it.

A baseline with no markers produces no valid diff, and every generation fails.

## Using your task

Replace the task in whichever entry script you are running:

```python
from src.evaluator import execute

task = KnapsackTask(n_items=30)
result = execute(task.baseline_program, task)
```

`main.py` and the experiment scripts construct `TSPTask` directly; swap that
line for your own class.

## Checking your task before you spend money

Score the baseline, then score something you know is worse. If they land close
together, your scoring function cannot tell them apart, and evolution has
nothing to climb.

```python
from src.evaluator import execute

task = KnapsackTask(n_items=20)

worse = task.baseline_program.replace(
    'key=lambda i: -items[i]["value"]', "key=lambda i: i"
)
print("baseline:", execute(task.baseline_program, task)["cost"])
print("worse:   ", execute(worse, task)["cost"])
```

A spread far larger than the run-to-run variation means the task is ready.

## See also

- [Evolution pipeline](evolution.md) — what happens to your task each generation
- [API reference](api/index.md) — exact signatures
