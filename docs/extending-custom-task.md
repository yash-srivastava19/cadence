# Extending Cadence with a Custom Task

Cadence is designed to be easily extensible. You can define your own optimization or code synthesis problem by subclassing the abstract `Task` interface.

## 1. Create a New Task Class

Inherit from `src.task.Task` and implement required methods:

```python
# src/tasks/my_custom_task.py
from src.task import Task
from src.models import EvaluationResult

class MyCustomTask(Task):
    @property
    def function_name(self) -> str:
        return "solve"

    @property
    def task_type(self):
        return TaskType.CUSTOM  # or define a new TaskType

    def generate_inputs(self, seed: int):
        # Generate test inputs deterministically
        random.seed(seed)
        return ...

    def evaluate(self, output, inputs) -> EvaluationResult:
        try:
            # Score your output, lower is better
            cost = ...
            return EvaluationResult(cost=cost, feasible=True)
        except Exception as e:
            return EvaluationResult(cost=float('inf'), feasible=False, error=str(e))

    @property
    def baseline_program(self) -> str:
        # Provide a working template with evolution markers
        return '''### START_BLOCK
# initial code
def solve(inputs):
    ...
### END_BLOCK'''
```

## 2. Register and Use in Experiments

Import your task in `main.py` or experiment scripts:

```python
from src.tasks.my_custom_task import MyCustomTask

task = MyCustomTask()
# Run evolution, evaluation, etc.
```

## 3. Tips and Best Practices

- Keep `generate_inputs` fast and deterministic.
- Provide clear baseline code with marked blocks.
- Use `EvaluationResult` for rich feedback (cost, feasible, error).
