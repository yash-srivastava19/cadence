# Advanced Features: Async Evaluation and CLI

This section covers Cadence's advanced capabilities, including asynchronous evaluation of programs and the built-in command-line interface.

## 1. Asynchronous Evaluation
Cadence can leverage Python's `asyncio` to run multiple evaluations concurrently, reducing overall runtime for batch assessments.

```python
import asyncio
from src.evaluator import Evaluator
from src.tasks.tsp_task import TSPTask

async def async_eval():
    evaluator = Evaluator()
    task = TSPTask(n_cities=8)
    seeds = list(range(5))
    # Run evaluations in parallel threads
    results = await asyncio.gather(*[
        asyncio.to_thread(evaluator.evaluate_code, task.baseline_program, task, [s])
        for s in seeds
    ])
    for i, res in enumerate(results):
        print(f"Seed {i}: cost={res.cost:.2f}, feasible={res.feasible}")

asyncio.run(async_eval())
```

## 2. Command-Line Interface (CLI)
Cadence provides a simple CLI via `main.py` for running experiments without modifying code.

```bash
# Run a TSP evolution for 10 generations and save results
gitbash
python main.py --task tsp --generations 10 --output evolution_results.sqlite
```

### CLI Options
- `--task`: Task name (e.g., `tsp`)
- `--generations`: Number of evolution generations
- `--population`: Population size per generation (default: 5)
- `--output`: Path to SQLite output database
- `--seeds`: Comma-separated random seeds for evaluation
