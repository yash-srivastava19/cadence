# Parallel evaluation

`execute()` already evaluates seeds concurrently. It submits one task per seed
to a `ThreadPoolExecutor` with `max_workers=min(len(seeds), 4)`, so the
default five-seed run uses four threads.

You do not need to arrange that yourself. This page covers the case where you
want to evaluate several *programs* at once — a batch of candidates, or a
sweep over task sizes.

```python
from concurrent.futures import ThreadPoolExecutor

from src.evaluator import execute
from src.tasks.tsp_task import TSPTask

tasks = [TSPTask(n_cities=n) for n in (10, 15, 20, 25)]
program = tasks[0].baseline_program

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(lambda t: execute(program, t), tasks))

for task, result in zip(tasks, results):
    print(f"{task.n_cities:3d} cities  cost {result['cost']:.2f}")
```

Threads are the right tool here only because the work is short and mostly
numeric. Two things to know before you scale it up:

- **Candidates share the interpreter.** `execute()` runs `exec()` in the
  calling process, so a candidate that mutates a global or seeds the `random`
  module affects everything running beside it. `TSPTask.generate_inputs()`
  calls `random.seed()` for exactly this reason, and it is a hazard, not a
  feature.
- **There is no timeout.** One candidate with an infinite loop wedges a worker
  permanently, and enough of them wedge the pool.

For genuinely independent evaluation you need separate processes. Cadence does
not provide that yet.

## Command line

There are no `--generations` or `--population` style flags. Every entry script
uses Hydra, which takes `KEY=value` arguments instead:

```bash
python run_h1_experiment.py GENERATIONS=60 LESSON_INTERVAL=3
```

See [Configuration](configuration.md) for every key each script reads.
