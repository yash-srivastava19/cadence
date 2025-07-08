# API Reference

Complete reference for all Cadence modules, classes, and functions.

## Core Modules

### src.task

Abstract base class for defining optimization problems.

#### Task

```python
class Task(ABC):
    """Abstract base class for defining optimization problems."""
```

**Abstract Methods:**

- `function_name() -> str`: Name of the function to extract from evolved code
- `generate_inputs(seed: int)`: Generate deterministic input for given seed
- `evaluate(output, input_data) -> float`: Evaluate output and return scalar cost
- `baseline_program() -> str`: Return default working solution with marked blocks

**Methods:**

- `is_feasible(output, *args) -> bool`: Check if output is feasible for the task

### src.evolve

Functions for applying code modifications during evolution.

#### apply_diff

```python
def apply_diff(parent_program: str, diffs: list[str]) -> str:
    """Apply list of diff code blocks into parent_program using START/END markers."""
```

**Parameters:**
- `parent_program`: Source code with marked evolution blocks
- `diffs`: List of code strings to replace marked blocks

**Returns:**
- Modified program with diffs applied to marked blocks

#### _apply_diff_in_strs

```python
def _apply_diff_in_strs(
    file_str: str,
    diffs: list[str],
    start_marker: str = "### START_BLOCK",
    end_marker: str = "### END_BLOCK"
) -> str:
    """Replace code blocks marked by custom start and end markers."""
```

**Parameters:**
- `file_str`: Source code string
- `diffs`: List of replacement code blocks
- `start_marker`: Block start marker (default: "### START_BLOCK")
- `end_marker`: Block end marker (default: "### END_BLOCK")

**Returns:**
- Modified code with replacements applied

### src.llm

Interface for Large Language Model interactions.

#### LLM

```python
class LLM:
    """Interface for Large Language Model providers."""

    def __init__(self, provider: str = "google", model: str = "gemini-pro"):
        """Initialize LLM with specified provider and model."""
```

**Methods:**

```python
def generate(self, prompt: str, **kwargs) -> str:
    """Generate text completion from prompt."""

def generate_diffs(
    self,
    parent_code: str,
    children_code: list[str],
    instructions: str
) -> list[str]:
    """Generate code diffs for program evolution."""

def count_tokens(self, text: str) -> int:
    """Count tokens in text string."""
```

**Parameters:**
- `prompt`: Input text prompt
- `parent_code`: Current program code
- `children_code`: List of previous child programs
- `instructions`: Evolution instructions for the LLM

### src.database

Database operations for storing evolution data.

#### Database

```python
class Database:
    """SQLite database interface for storing evolution data."""

    def __init__(self, db_path: str = "cadence_db.sqlite"):
        """Initialize database connection."""
```

**Methods:**

```python
def add_program(
    self,
    code: str,
    generation: int,
    parent_id: int = None,
    cost: float = None,
    feasible: bool = None
) -> int:
    """Add program to database and return program ID."""

def get_program(self, program_id: int) -> dict:
    """Retrieve program by ID."""

def get_generation_programs(self, generation: int) -> list[dict]:
    """Get all programs from specific generation."""

def get_best_programs(self, limit: int = 10) -> list[dict]:
    """Get best performing programs."""

def update_program_metrics(
    self,
    program_id: int,
    cost: float,
    feasible: bool,
    execution_time: float = None
):
    """Update program performance metrics."""

def get_evolution_history(self) -> list[dict]:
    """Get complete evolution history."""
```

### src.evaluator

Program evaluation and execution.

#### Evaluator

```python
class Evaluator:
    """Evaluates program performance on tasks."""

    def __init__(self, task: Task, timeout: int = 30):
        """Initialize evaluator with task and timeout."""
```

**Methods:**

```python
def evaluate_program(
    self,
    program_code: str,
    num_seeds: int = 5
) -> dict:
    """Evaluate program on multiple test cases."""

def extract_function(self, code: str, function_name: str):
    """Extract named function from code string."""

def safe_execute(self, func, inputs, timeout: int = None):
    """Safely execute function with timeout and error handling."""
```

**Returns:**
- Dictionary with evaluation results including cost, feasibility, and metrics

### src.prompt_sampler

Prompt generation for LLM interactions.

#### PromptSampler

```python
class PromptSampler:
    """Generates prompts for LLM-based code evolution."""

    def __init__(self, task: Task):
        """Initialize with task instance."""
```

**Methods:**

```python
def sample_prompt(
    self,
    parent_program: str,
    children_programs: list[str] = None,
    instructions: str = None
) -> str:
    """Generate evolution prompt for LLM."""

def generate_instructions(self, generation: int, best_cost: float) -> str:
    """Generate dynamic instructions based on evolution progress."""

def format_code_block(self, code: str, language: str = "python") -> str:
    """Format code for inclusion in prompts."""
```

## Task Implementations

### src.tasks.tsp_task

Traveling Salesman Problem implementation.

#### TSPTask

```python
class TSPTask(Task):
    """Traveling Salesman Problem task implementation."""

    def __init__(self, n_cities: int = 10):
        """Initialize TSP task with specified number of cities."""
```

**Properties:**
- `function_name`: Returns "tsp"
- `baseline_program`: Basic TSP solution template

**Methods:**

```python
def generate_inputs(self, seed: int) -> list[tuple[float, float]]:
    """Generate random city coordinates."""

def evaluate(self, output: list[int], cities: list[tuple]) -> dict:
    """Evaluate TSP tour and return cost."""

def is_feasible(self, output: list[int], cities: list[tuple]) -> bool:
    """Check if tour is a valid permutation."""
```

## Utility Functions

### Helper Functions

```python
def extract_code_blocks(code: str, markers: tuple[str, str]) -> list[str]:
    """Extract code between specified markers."""

def validate_program_syntax(code: str) -> tuple[bool, str]:
    """Validate Python syntax and return (is_valid, error_message)."""

def calculate_distance(city1: tuple[float, float], city2: tuple[float, float]) -> float:
    """Calculate Euclidean distance between two cities."""

def normalize_tour(tour: list[int]) -> list[int]:
    """Normalize tour to start from city 0."""
```

## Configuration

### Environment Variables

- `GOOGLE_API_KEY`: Google Gemini API key
- `CADENCE_DB_PATH`: Database file path (default: "cadence_db.sqlite")
- `CADENCE_LOG_LEVEL`: Logging level (DEBUG, INFO, WARN, ERROR)
- `CADENCE_TIMEOUT`: Default execution timeout in seconds

### Configuration Files

Configuration can be loaded from JSON files:

```python
{
    "evolution": {
        "population_size": 20,
        "generations": 100,
        "mutation_rate": 0.8
    },
    "llm": {
        "provider": "google",
        "model": "gemini-pro",
        "temperature": 0.7,
        "max_tokens": 2048
    },
    "evaluation": {
        "timeout": 30,
        "num_seeds": 10,
        "parallel": true
    }
}
```

## Error Handling

### Custom Exceptions

```python
class CadenceError(Exception):
    """Base exception for Cadence-specific errors."""

class TaskError(CadenceError):
    """Raised when task operations fail."""

class LLMError(CadenceError):
    """Raised when LLM operations fail."""

class DatabaseError(CadenceError):
    """Raised when database operations fail."""

class EvaluationError(CadenceError):
    """Raised when program evaluation fails."""
```

### Error Codes

- `TASK_001`: Invalid task configuration
- `LLM_001`: API key not found
- `LLM_002`: Rate limit exceeded
- `LLM_003`: Invalid response format
- `DB_001`: Database connection failed
- `DB_002`: Query execution failed
- `EVAL_001`: Program compilation failed
- `EVAL_002`: Execution timeout
- `EVAL_003`: Runtime error

## Type Hints

Complete type definitions for all public APIs:

```python
from typing import Dict, List, Optional, Tuple, Union, Any

ProgramCode = str
Cost = float
Generation = int
ProgramID = int
EvaluationResult = Dict[str, Union[float, bool, Dict[str, Any]]]
Cities = List[Tuple[float, float]]
Tour = List[int]
```

## Constants

```python
# Default configuration values
DEFAULT_POPULATION_SIZE = 10
DEFAULT_GENERATIONS = 50
DEFAULT_TIMEOUT = 30
DEFAULT_NUM_SEEDS = 5

# Database schema version
DB_VERSION = "1.0.0"

# Supported LLM providers
SUPPORTED_PROVIDERS = ["google", "openai"]

# Code block markers
START_MARKER = "### START_BLOCK"
END_MARKER = "### END_BLOCK"
```
