# The evolution pipeline

What happens between one generation and the next, in the order it happens.
Every step below names the function that does it.

## One generation

| # | Step | Function |
| --- | --- | --- |
| 1 | Choose a parent | `sample()` or `get_best_program()`, `src/database.py` |
| 2 | Build a prompt | `build()`, `src/prompt_sampler.py` |
| 3 | Ask for a new block | `generate()`, `src/llm.py` |
| 4 | Swap it into the parent | `apply_diff()`, `src/evolve.py` |
| 5 | Score the child | `execute()`, `src/evaluator.py` |
| 6 | Store it | `add()`, `src/database.py` |

There is no population array. The database *is* the population, and a
generation is a column in it.

## 1. Choosing a parent

Two paths, chosen by generation number.

**Tournament, most generations.** `sample_parent()` draws
`tournament_size` programs uniformly at random from the previous generation
and returns the one with the lowest cost. `DEFAULT_TOURNAMENT_SIZE` is `3`.

```text
SELECT ... FROM (SELECT * FROM programs WHERE generation_number = ?
                 ORDER BY RANDOM() LIMIT ?) ORDER BY metric ASC LIMIT 1
```

A tournament size of `1` is plain uniform sampling — no selection pressure at
all. Larger values push harder towards the current best and explore less.

**Elitism, every `ELITISM_INTERVAL` generations.** `get_best_program()`
returns the lowest-cost program from the whole run, ignoring generations.
Without this, a good lineage can be lost to drift.

Alongside the parent, `sample()` returns its existing children. They go into
the prompt as previous attempts, so the model can be told not to repeat them.

## 2. Building the prompt

`build(parent_program, inspirations, lesson)` assembles four parts:

1. A fixed instruction: improve efficiency, solution quality, and
   generalisation; change only what is between the markers; return the same
   number of blocks.
2. The guiding lesson, if one exists.
3. The parent's code and its cost, under `### CURRENT BASELINE SOLUTION`.
4. The sibling programs and their costs, under `### PREVIOUS ATTEMPTS`, with
   an explicit instruction to try a fundamentally different idea.

`parent_program` is a tuple from the database: index `3` is the code, index
`4` is the cost.

```python
from src.prompt_sampler import build
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)
parent = (0, None, None, task.baseline_program, None)
print(build(parent, inspirations=[], lesson=None))
```

The costs shown to the model are single floats. Failed programs appear as
`1e8` with no explanation, because the error text is discarded when
`execute()` aggregates across seeds. The model can see *that* something
failed, never *why*.

## 3 and 4. Mutation

The model is asked to return the marked blocks, rewritten.
`_extract_code_blocks()` pulls the body out of each
`### START_BLOCK` / `### END_BLOCK` region in the response, and
`apply_diff()` substitutes the Nth body for the Nth block of the parent.

**It is positional whole-block replacement, not a diff.** The function is
named `apply_diff` but there is no search text, no context matching, and no
line-level merge. Consequences worth knowing:

- A response with fewer blocks than the parent leaves the remaining blocks
  untouched, silently. The prompt's "You MUST output the same number of
  blocks" is what guards against this, and nothing enforces it.
- A response with more blocks has the extras ignored.
- A response with no markers at all yields no child. The generation is logged
  as failed, and the attempt is spent.

This is the only mutation operator. There is no crossover between two parents,
so every child differs from exactly one parent.

## 5. Scoring

`execute()` runs the child's source with `exec()`, pulls out
`task.function_name`, and scores it on five seeds across four threads.

It returns the mean cost and the fraction of seeds that were feasible. A
program is treated as feasible when more than half its seeds pass. Anything
that fails to load, fails to run, or returns a non-finite cost gets
`INFEASIBLE_COST`, which is `1e8`.

Because the seeds are fixed, costs are comparable across generations. That is
the whole reason `generate_inputs` must be deterministic.

## Lessons and meta-prompting

Two feedback loops run on top of the main one.

**Lessons**, every `LESSON_INTERVAL` generations.
`get_lesson_from_history()` sends the last N log entries to the model and asks
what it has learned. The answer is prepended to later prompts and appended to
`lesson_history.json`.

The entries it sends are formatted by `format_generation_entry()`, which emits
`Cost: {cost} | Feasibility: {feasibility}` and the code. Summary statistics,
not failure detail — so the lesson is drawn from what scored well, not from
what went wrong and why.

**Instruction mutation**, every `META_PROMPT_EDIT_INTERVAL` generations.
`mutate_instruction()` asks the model to rewrite the fixed instruction text,
and `update_instruction()` swaps it in. The system edits its own prompt.

Only `main.py` does this. `run_h1_experiment.py` and `run_h2_experiment.py`
keep their instruction fixed.

## What this pipeline is not

Naming the gaps, because the vocabulary of evolutionary computation implies
machinery that is not here.

- **No islands.** One population, no subpopulations, no migration.
- **No archive.** Nothing is retired or capped; the database grows forever.
- **No novelty pressure.** Two candidates with identical behaviour both
  survive. Programs are hashed in `run_h1_experiment.py`, but the hash is
  recorded rather than used to reject duplicates.
- **No multi-objective selection.** One float, minimised.
- **No sandbox and no timeout.** See [Evaluating programs](performance-evaluation.md#what-it-does-not-do).

## See also

- [Tasks](tasks.md) — the interface each step calls into
- [Configuration](configuration.md) — the intervals named above
- [LLM interaction](llm-interaction.md) — what is asked of the model
