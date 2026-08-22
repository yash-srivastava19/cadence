# API reference

Every signature on this page is checked against the source by
`tests/test_docs.py`. If a name here does not exist, CI fails.

Two layers are documented separately, because they are at different stages:

- **`src/`** — what runs today. Everything below.
- **`cadence/`** — the framework being built to replace it. Not usable yet;
  see [Architecture](../architecture.md).

## `src.evaluator`

Turning source code into a cost.

```python
from src.evaluator import execute, evaluate_on_task, INFEASIBLE_COST
```

| Name | Signature | Returns |
| --- | --- | --- |
| `execute` | `(child_program_code, task, seeds=None)` | `{"cost": float, "feasibility": float}` |
| `evaluate_on_task` | `(func, task, seed)` | `{"cost", "feasible", "error"}` |
| `INFEASIBLE_COST` | constant | `1e8` |

`execute()` is the supported entry point. It runs `exec()` on the source,
retrieves `task.function_name`, scores it on `seeds` (default
`[1, 2, 3, 4, 5]`) across `min(len(seeds), 4)` threads, and returns the mean
cost with the fraction of seeds that were feasible.

`evaluate_on_task()` scores a single seed and **keeps the error text**, which
`execute()` discards when aggregating. Use it to debug a task.

Also present, TSP-specific despite living in the generic module:
`euclidean_distance(a, b)`, `compute_total_distance(tour, cities)`,
`generate_test_instance(n=None, seed=None)`, and
`execute_single_seed(seed, func, n_cities=10)`.

`Evaluator` is a class with `evaluate_code(code, task, seeds=None)`. It
duplicates `execute()`, nothing in the repository calls it, and its `timeout`
and `max_memory_mb` constructor arguments are stored but never read. Prefer
`execute()`.

## `src.task`

```python
from src.task import Task
```

The abstract base every problem implements. Four required members and two
optional ones — [Tasks](../tasks.md) is the guide.

| Member | Kind | Signature |
| --- | --- | --- |
| `function_name` | abstract property | `-> str` |
| `generate_inputs` | abstract method | `(seed) -> Any` |
| `evaluate` | abstract method | `(output, input_data) -> EvaluationResult` |
| `baseline_program` | abstract property | `-> str` |
| `task_type` | property | `-> TaskType`, defaults to `CUSTOM` |
| `is_feasible` | method | `(output, input_data=None, **kwargs) -> bool`, defaults `True` |
| `create_instance` | method | `(seed, **kwargs) -> TaskInstance` |
| `validate_output_format` | method | `(output) -> bool`, defaults `True` |

## `src.tasks.tsp_task`

```python
from src.tasks.tsp_task import TSPTask
```

`TSPTask(n_cities=10)` — raises `ValueError` below three cities.
`function_name` is `"tsp"`, `task_type` is `TaskType.TSP`. `generate_inputs`
returns a list of `(x, y)` tuples in the range 0–100.

`get_optimal_tour_length(cities)` currently returns `None` for every input.

## `src.evolve`

```python
from src.evolve import apply_diff, extract_blocks, count_blocks
```

| Name | Signature |
| --- | --- |
| `apply_diff` | `(parent_program, diffs) -> str` |
| `apply_single_diff` | `(parent_program, diff, block_index=0, start_marker=..., end_marker=...)` |
| `extract_blocks` | `(code, start_marker=..., end_marker=...) -> List[str]` |
| `count_blocks` | `(code, start_marker=..., end_marker=...) -> int` |
| `validate_block_structure` | `(code, start_marker=..., end_marker=...) -> bool` |

Markers default to `### START_BLOCK` and `### END_BLOCK`.

`apply_diff` replaces the Nth marked block with the Nth string in `diffs` —
positional whole-block substitution, not a textual diff. Extra strings are
ignored; missing ones leave blocks unchanged. Raises `EvolutionError`.

## `src.llm`

```python
from src.llm import LLMProvider, LLMConfig, generate
```

`LLMConfig` is a dataclass: `model="gemini-2.0-flash"`, `timeout=30.0`,
`max_retries=3`.

`LLMProvider(config=None)` reads `GEMINI_API_KEY` at construction and raises
`LLMError` if it is unset.

| Method | Signature | Returns |
| --- | --- | --- |
| `generate_code` | `(prompt)` | `List[CodeBlock]` |
| `mutate_instruction` | `(base_instruction)` | `str` |
| `generate_lesson` | `(meta_prompt)` | `str` |
| `validate_response` | `(response_text)` | `bool` |

Module-level `generate(prompt) -> List[str]`,
`mutate_instruction(base_instruction) -> str`,
`generate_lessons(meta_prompt) -> str`, and `extract_valid_blocks(text)` wrap
these for callers that do not hold a provider.

## `src.prompt_sampler`

```python
from src.prompt_sampler import build, update_instruction
```

`build(parent_program, inspirations, lesson=None) -> str`.

`parent_program` is annotated `Dict[str, Any]` but accepts a tuple or list
too, which is what the runtime passes: index `3` is the code, index `4` is the
cost. Raises `PromptError` on empty code.

`update_instruction(new_instruction)` mutates the module-level instruction
template used by later `build()` calls.

## `src.meta_prompting`

```python
from src.meta_prompting import get_lesson_from_history
```

| Name | Signature |
| --- | --- |
| `get_lesson_from_history` | `(logs, N=2, previous_lesson=None, llm_provider=None) -> Optional[str]` |
| `format_generation_entry` | `(entry, feedback=None) -> str` |
| `update_lesson_history` | `(lesson_history, new_lesson, generation)` |
| `get_recent_lessons_text` | `(lesson_history, n=3) -> str` |

`format_generation_entry` emits `Cost: {cost} | Feasibility: {feasibility}`
plus the code — summary statistics, no failure detail.

## `src.database`

```python
from src.database import Database, add, sample, get_best_program
```

### Module functions

These are what the entry scripts use. They open a `Database` on
`cadence_db.sqlite` per call.

| Name | Signature |
| --- | --- |
| `add` | `(program_code, metric, parent_id=None, instance_id=None, diff=None, prompt=None) -> int` |
| `sample` | `(generation_number=0, tournament_size=3) -> (Optional[Tuple], List[Tuple])` |
| `get_best_program` | `(generation_limit=None) -> Optional[Tuple]` |
| `get_all_programs` | `() -> List[Tuple]` |
| `add_instance` | `(seed) -> int` |

Tuples are `(id, generation, parent_id, code, metric)`.

### `Database`

`Database(config=None)` takes a `DatabaseConfig`. Methods return
`ProgramEntry` objects rather than tuples.

| Method | Signature |
| --- | --- |
| `add_program` | `(code, metric, generation, parent_id=None, instance_id=None, diff=None, prompt=None) -> int` |
| `get_program` | `(program_id) -> Optional[ProgramEntry]` |
| `sample_parent` | `(generation=0, tournament_size=3) -> Optional[ProgramEntry]` |
| `get_children` | `(parent_id) -> List[ProgramEntry]` |
| `get_best_program` | `(generation_limit=None) -> Optional[ProgramEntry]` |
| `get_generation_summary` | `(generation) -> Optional[GenerationSummary]` |
| `get_all_programs` | `() -> List[ProgramEntry]` |
| `add_instance` | `(instance) -> int` |
| `create_run` | `(run_id, experiment_config)` |
| `get_run_summary` | `(run_id) -> Optional[Dict[str, Any]]` |

Raises `DatabaseError`.

## `src.models`

Pydantic models. The ones you will touch:

| Model | Fields |
| --- | --- |
| `EvaluationResult` | `cost`, `feasible`, `error=None`, `execution_time=None`, `memory_usage=None` |
| `ProgramEntry` | `id`, `generation`, `parent_id`, `code`, `metric`, `instance_id`, `diff`, `prompt`, `timestamp` |
| `DatabaseConfig` | `database_path="cadence_db.sqlite"`, `connection_timeout=30.0`, `enable_wal_mode=True` |
| `TaskType` | `TSP`, `KNAPSACK`, `CUSTOM` |

`EvaluationResult` is frozen and rejects a negative `cost`.

## Exceptions

| Exception | Raised by |
| --- | --- |
| `EvaluationError` | `src.evaluator` |
| `EvolutionError` | `src.evolve` |
| `LLMError` | `src.llm` |
| `PromptError` | `src.prompt_sampler` |
| `DatabaseError` | `src.database` |

## Configuration

There are no `CADENCE_*` environment variables. The only one Cadence reads is
`GEMINI_API_KEY` — see [Configuration](../configuration.md).
