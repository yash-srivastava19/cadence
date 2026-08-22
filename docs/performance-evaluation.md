# Evaluating programs

`src/evaluator.py` turns a program's source into a cost. It is the piece that
decides what evolution climbs towards.

## The function you want

`execute()` is the supported entry point. Every script in the repository uses
it.

```python
from src.evaluator import execute
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)
print(execute(task.baseline_program, task))
```

```text
{'cost': 580.2647322648497, 'feasibility': 1.0}
```

| Key | Meaning |
| --- | --- |
| `cost` | Mean cost across the seeds. `1e8` if the program failed to load or run |
| `feasibility` | Fraction of seeds that produced a valid answer, 0.0 to 1.0 |

Pass your own seeds to change what it is scored on:

```python
from src.evaluator import execute
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)
print(execute(task.baseline_program, task, seeds=[7, 8, 9]))
```

The default is `[1, 2, 3, 4, 5]`, run across at most four threads.

## Scoring one seed, with the error text

`execute()` discards the reason a seed failed. When you are debugging a task,
call the single-seed function directly — it keeps the message.

```python
from src.evaluator import evaluate_on_task
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)
namespace = {}
exec(task.baseline_program, namespace)
solver = namespace[task.function_name]

print(evaluate_on_task(solver, task, seed=1))
```

```text
{'cost': 714.7484534035748, 'feasible': True, 'error': None}
```

On failure, `error` carries the exception text. That is the fastest way to
find out why a task is scoring everything at `1e8`.

## What it does not do

Read this before pointing Cadence at anything sensitive.

- **No isolation.** `execute()` calls `exec()` on the candidate in the current
  Python process. A generated program can read your files, your environment,
  and the network.
- **No timeout.** An infinite loop in a candidate hangs the run. `Evaluator`
  takes `timeout` and `max_memory_mb` arguments, stores them on the instance,
  and never reads them again.
- **No memory cap.** A candidate that allocates without bound takes the whole
  process with it.

Run Cadence only on code and tasks you would be willing to execute by hand on
the same machine.

## The `Evaluator` class

`src/evaluator.py` also defines an `Evaluator` class with an `evaluate_code()`
method. It duplicates `execute()` and nothing in the repository calls it.
Prefer `execute()`.
