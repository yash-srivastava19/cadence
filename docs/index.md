# Cadence

Cadence improves a program by rewriting it over and over. A language model
proposes an edit, Cadence runs the result against a scoring function you
provide, keeps what scored better, and repeats.

You supply two things: a program with the editable region marked, and a way to
score it. Cadence supplies the loop.

## Try it in five minutes

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
uv sync
export GEMINI_API_KEY="your-key-here"
python run_h1_experiment.py
```

That evolves a Traveling Salesman heuristic for 30 generations, then writes
`h1_results.png` and `experiment_log.json` to the project root. It costs
roughly 30 Gemini calls.

New here? [Getting started](getting-started.md) walks through the same run and
explains what each part of the output means.

## How one generation works

1. **Sample a parent.** Usually a program from the previous generation; every
   `ELITISM_INTERVAL` generations, the best program found so far.
2. **Build a prompt** from the parent, a few sibling programs as inspiration,
   and the current lesson.
3. **Ask the model to rewrite the marked block** — just that block, not the
   whole file.
4. **Swap it into the parent**, block for block, in order.
5. **Score the child** on five fixed seeds, in parallel.
6. **Store it** in SQLite with its cost, its parent, and the diff that made it.

Every `LESSON_INTERVAL` generations, Cadence asks the model what it has learned
from the run so far and prepends that to later prompts. Every
`META_PROMPT_EDIT_INTERVAL` generations, it rewrites its own instruction text.

## What you need to write

Two things, both in your own code:

- **A baseline program** with the region to evolve wrapped in
  `### START_BLOCK` and `### END_BLOCK`. Everything outside the markers is
  fixed and the model is told not to touch it.
- **A `Task` subclass** with four members: `function_name`, `generate_inputs`,
  `evaluate`, and `baseline_program`.

[Tasks](tasks.md) is the complete guide, with a worked knapsack example.

## What Cadence does not do yet

Stated plainly, because finding out later wastes your time:

- **One provider.** Google Gemini only. `LLMConfig.model` defaults to
  `gemini-2.0-flash`.
- **One objective.** `EvaluationResult.cost` is a single float, lower is
  better. There is no Pareto or multi-objective selection.
- **Diffs only.** No crossover, no full-file rewrite operator.
- **No sandbox.** Candidate programs run with `exec()` inside the same Python
  process as the loop. Do not point Cadence at anything you would not run by
  hand on the same machine.
- **No timeout.** A candidate containing an infinite loop hangs the run.
  `Evaluator` accepts `timeout` and `max_memory_mb` arguments and currently
  ignores both.

The [architecture](architecture.md) page covers the design; the parts marked
as planned are not built.

## Where to go next

| You want to | Read |
| --- | --- |
| Run Cadence for the first time | [Getting started](getting-started.md) |
| Apply it to your own problem | [Tasks](tasks.md) |
| Change generations, seeds, intervals | [Configuration](configuration.md) |
| Understand selection and lessons | [Evolution pipeline](evolution.md) |
| Reproduce the published experiments | [Experiments](experiments.md) |
| Watch a run in the browser | [Web interface](web-interface.md) |
| Look up a function signature | [API reference](api/index.md) |
| Send a patch | [Contributing](contributing.md) |

## Licence

MIT. See [LICENSE](https://github.com/yash-srivastava19/cadence/blob/main/LICENSE).
