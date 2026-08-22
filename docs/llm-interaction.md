# LLM interaction

Cadence talks to exactly one provider: Google Gemini, through
[`google-genai`](https://pypi.org/project/google-genai/). `src/llm.py` holds
all of it.

## Configuration

`LLMConfig` is a dataclass with defaults, and nothing overrides it from a
config file today. To change the model, pass a config or edit the default.

```python
from src.llm import LLMConfig, LLMProvider

provider = LLMProvider(LLMConfig(model="gemini-2.0-flash", max_retries=3))
```

| Field | Default | Notes |
| --- | --- | --- |
| `model` | `"gemini-2.0-flash"` | Any Gemini model id |
| `timeout` | `30.0` | Seconds |
| `max_retries` | `3` | Attempts before `LLMError` |

Authentication is the `GEMINI_API_KEY` environment variable, read in
`_initialize_client()`. `load_dotenv()` runs at import, so a `.env` at the
project root works too. There is no `GOOGLE_API_KEY` and no `GENAI_API_KEY`.

## The three things Cadence asks for

| Method | Asks for | Returns |
| --- | --- | --- |
| `generate_code(prompt)` | a mutation of the marked block | `List[CodeBlock]` |
| `mutate_instruction(base)` | a rewrite of the instruction text | `str` |
| `generate_lesson(meta_prompt)` | what the run has learned so far | `str` |

Module-level `generate()`, `mutate_instruction()`, and `generate_lessons()`
wrap these for scripts that do not want to hold a provider.

## Building a prompt

`build()` takes the parent program, a list of inspiration programs, and the
current lesson.

```python
from src.prompt_sampler import build
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)

# A parent is (id, parent_id, instance_id, code, cost)
parent = (0, None, None, task.baseline_program, None)
prompt = build(parent, inspirations=[], lesson=None)
print(prompt)
```

`parent_program` is annotated `Dict[str, Any]` but accepts a tuple or list as
well, and the runtime path uses tuples straight out of the database. Index 3
is the code and index 4 is the cost.

## What comes back

The model is asked for `SEARCH`/`REPLACE` pairs, not a whole file.
`src/evolve.py` applies them with `apply_diff()`, which only rewrites text
between `### START_BLOCK` and `### END_BLOCK`. A response that does not parse
produces no child, and the generation is skipped.

## Limits

- One provider, one model at a time. No ensemble, no fallback.
- No cost or token accounting. Nothing records what a run spent.
- Retries are counted but not classified: a 401 burns the same attempts as a
  timeout.
