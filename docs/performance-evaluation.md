# Program Performance Evaluation

This section covers how to use the `Evaluator` to assess generated code for optimization tasks.

## Modules

- **`src.evaluator.Evaluator`**: Main class for evaluating code snippets.
- **`execute_single_seed`**: Helper for single-run metrics.
- **`compute_total_distance`**: Example utility for TSP tasks.

## Usage Example

```python
from src.database import Database, DatabaseConfig
from src.evaluator import Evaluatorrom src.tasks.tsp_task import TSPTask

# Load database of evolved programs
db = Database(DatabaseConfig(database_path='evolution.db'))
entries = db.get_all_programs()

evaluator = Evaluator()
task = TSPTask(n_cities=10)

for entry in entries:
    code = entry.code
    gen = entry.generation_number
    result = evaluator.evaluate_code(code, task, seeds=[0,1,2])
    print(f"Generation {gen}: cost={result.cost:.2f}, feasible={result.feasible}")
```

## Configuration

Adjust timeouts and memory limits via `Evaluator(timeout=60.0, max_memory_mb=256)`.
