# Tasks

Tasks define the optimization problems that Cadence can solve. This document explains how to create custom tasks and work with existing ones.

## Task Interface

All tasks inherit from the abstract `Task` class:

```python
from abc import ABC, abstractmethod

class Task(ABC):
    @property
    @abstractmethod
    def function_name(self) -> str:
        """Name of the function to extract from evolved code."""

    @abstractmethod
    def generate_inputs(self, seed: int):
        """Generate deterministic input for a given seed."""

    @abstractmethod
    def evaluate(self, output, input_data) -> float:
        """Evaluate function output, return scalar cost (lower=better)."""

    @property
    @abstractmethod
    def baseline_program(self) -> str:
        """Return default working solution with marked blocks."""

    def is_feasible(self, output, *args) -> bool:
        """Check if output is feasible (override if needed)."""
        return True
```

## Built-in Tasks

### TSP Task

The Traveling Salesman Problem task is included as a reference implementation.

```python
from src.tasks.tsp_task import TSPTask

# Create TSP task with 10 cities
task = TSPTask(n_cities=10)

# Generate test input
cities = task.generate_inputs(seed=42)
# Returns: [(x1, y1), (x2, y2), ..., (x10, y10)]

# Evaluate a solution
tour = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
result = task.evaluate(tour, cities)
# Returns: {"cost": 245.67, "feasible": True}
```

**TSP Features:**
- Configurable number of cities
- Euclidean distance calculation
- Feasibility checking (valid permutation)
- Deterministic city placement

## Creating Custom Tasks

### Step 1: Define the Problem

Create a new task class inheriting from `Task`:

```python
# src/tasks/knapsack_task.py
import random
from src.task import Task

class KnapsackTask(Task):
    def __init__(self, n_items=20, capacity=100):
        self.n_items = n_items
        self.capacity = capacity

    @property
    def function_name(self):
        return "knapsack"
```

### Step 2: Implement Input Generation

Generate deterministic test cases:

```python
def generate_inputs(self, seed: int):
    random.seed(seed)

    # Generate items: (weight, value) pairs
    items = []
    for _ in range(self.n_items):
        weight = random.randint(1, 20)
        value = random.randint(1, 100)
        items.append((weight, value))

    return {
        "items": items,
        "capacity": self.capacity
    }
```

### Step 3: Implement Evaluation

Define how solutions are scored:

```python
def evaluate(self, output, input_data) -> float:
    items = input_data["items"]
    capacity = input_data["capacity"]

    if not self.is_feasible(output, input_data):
        return {"cost": float("inf"), "feasible": False}

    # Calculate total weight and value
    total_weight = sum(items[i][0] for i in output)
    total_value = sum(items[i][1] for i in output)

    # Return negative value (since lower cost = better)
    return {"cost": -total_value, "feasible": True}

def is_feasible(self, output, input_data):
    items = input_data["items"]
    capacity = input_data["capacity"]

    # Check valid indices
    if not all(0 <= i < len(items) for i in output):
        return False

    # Check capacity constraint
    total_weight = sum(items[i][0] for i in output)
    return total_weight <= capacity
```

### Step 4: Define Baseline Program

Provide a working template with marked evolution blocks:

```python
@property
def baseline_program(self) -> str:
    return '''
def knapsack(items, capacity):
    """Solve knapsack problem."""
    ### START_BLOCK
    # Simple greedy approach: highest value first
    n = len(items)
    indices = list(range(n))
    indices.sort(key=lambda i: items[i][1], reverse=True)

    selected = []
    current_weight = 0

    for i in indices:
        weight, value = items[i]
        if current_weight + weight <= capacity:
            selected.append(i)
            current_weight += weight

    return selected
    ### END_BLOCK
'''
```

### Step 5: Register and Use

```python
# In main.py or experiment script
from src.tasks.knapsack_task import KnapsackTask

task = KnapsackTask(n_items=50, capacity=200)
# Use with evolution system...
```

## Task Design Guidelines

### Input Generation

**Use Deterministic Seeds:**
```python
def generate_inputs(self, seed: int):
    random.seed(seed)  # Ensures reproducible inputs
    # Generate test case...
```

**Return Structured Data:**
```python
# Good: structured dictionary
return {
    "nodes": graph_nodes,
    "edges": graph_edges,
    "constraints": constraints
}

# Avoid: positional arguments
return graph_nodes, graph_edges, constraints
```

### Evaluation Metrics

**Return Detailed Results:**
```python
def evaluate(self, output, input_data) -> dict:
    return {
        "cost": primary_objective,
        "feasible": is_valid,
        "secondary_metrics": {
            "execution_time": time_taken,
            "memory_usage": memory_used
        }
    }
```

**Handle Edge Cases:**
```python
def evaluate(self, output, input_data) -> dict:
    # Handle None/invalid output
    if output is None:
        return {"cost": float("inf"), "feasible": False}

    # Handle exceptions gracefully
    try:
        cost = compute_cost(output, input_data)
    except Exception as e:
        return {"cost": float("inf"), "feasible": False, "error": str(e)}

    return {"cost": cost, "feasible": True}
```

### Baseline Programs

**Include Evolution Blocks:**
```python
@property
def baseline_program(self) -> str:
    return '''
def solve_problem(input_data):
    """Problem description."""

    ### START_BLOCK
    # Initial solution approach
    # This block will be evolved by LLM
    ### END_BLOCK

    # Helper functions (not evolved)
    def helper_function():
        pass

    ### START_BLOCK
    # Another evolvable section
    ### END_BLOCK
'''
```

**Provide Working Solutions:**
Ensure the baseline program runs without errors:

```python
# Test your baseline
task = YourTask()
baseline = task.baseline_program
inputs = task.generate_inputs(42)

# This should work
exec(baseline)
result = solve_problem(inputs)
evaluation = task.evaluate(result, inputs)
assert evaluation["feasible"] == True
```

## Multi-Objective Tasks

For problems with multiple objectives:

```python
class MultiObjectiveTask(Task):
    def evaluate(self, output, input_data) -> dict:
        obj1 = compute_objective1(output, input_data)
        obj2 = compute_objective2(output, input_data)

        # Weighted combination
        cost = 0.7 * obj1 + 0.3 * obj2

        return {
            "cost": cost,
            "feasible": self.is_feasible(output, input_data),
            "objectives": {
                "obj1": obj1,
                "obj2": obj2
            }
        }
```

## Testing Tasks

Create comprehensive tests for your tasks:

```python
# tests/tasks/test_knapsack_task.py
import pytest
from src.tasks.knapsack_task import KnapsackTask

class TestKnapsackTask:
    def test_input_generation(self):
        task = KnapsackTask(n_items=10)
        inputs = task.generate_inputs(42)

        assert len(inputs["items"]) == 10
        assert inputs["capacity"] == 100

        # Test determinism
        inputs2 = task.generate_inputs(42)
        assert inputs == inputs2

    def test_evaluation(self):
        task = KnapsackTask(n_items=5, capacity=50)
        inputs = task.generate_inputs(1)

        # Test valid solution
        solution = [0, 2, 4]  # Select some items
        result = task.evaluate(solution, inputs)
        assert result["feasible"] == True
        assert isinstance(result["cost"], (int, float))

    def test_feasibility(self):
        task = KnapsackTask(n_items=5, capacity=10)
        inputs = {
            "items": [(5, 10), (3, 6), (4, 8), (2, 4), (6, 12)],
            "capacity": 10
        }

        assert task.is_feasible([0, 1], inputs) == True   # weight=8, ok
        assert task.is_feasible([0, 4], inputs) == False  # weight=11, too heavy
        assert task.is_feasible([5], inputs) == False     # invalid index
```

## Best Practices

1. **Keep it Simple**: Start with basic implementations and iterate
2. **Test Thoroughly**: Ensure baseline programs work correctly
3. **Document Well**: Clear docstrings and comments
4. **Handle Errors**: Graceful handling of invalid outputs
5. **Use Type Hints**: Better code clarity and IDE support
6. **Benchmark**: Compare evolved solutions against known optimal ones
