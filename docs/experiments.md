# Experiments

Two experiment scripts ship with Cadence. They answer two different questions
and are the reproducible artefacts behind the plots in the README.

Neither uses a framework class. Each is a script with a `@hydra.main`
entrypoint, and you configure it with [Hydra keys](configuration.md).

## H1 — does evolution beat a hand-written heuristic?

```bash
python run_h1_experiment.py
```

Runs `GENERATIONS` generations against a fixed TSP instance set, alongside two
reference heuristics computed by `run_baselines()`: nearest-neighbour and a
reversal heuristic. Writes `h1_results.png` and `experiment_log.json`.

The plot is the answer. If the evolved curve does not get under both
reference lines, evolution did not beat a heuristic somebody could have
written in ten minutes.

| Key | Default | Effect |
| --- | --- | --- |
| `GENERATIONS` | 30 | Length of the run, and roughly the number of model calls |
| `SEEDS` | 3 | TSP instances used to score the baselines |
| `ELITISM_INTERVAL` | 5 | How often to breed from the best-so-far |
| `LESSON_INTERVAL` | 5 | How often to extract a lesson |
| `API_MAX_RETRIES` | 2 | Attempts per model call before skipping the generation |
| `API_TIMEOUT` | 100 | Seconds per model call |

## H2 — does the advantage hold as the problem grows?

```bash
python run_h2_experiment.py
```

Repeats the whole evolution at each size in `SIZES`, and compares the final
evolved cost against the nearest-neighbour baseline at that size. Writes
`h2_log_size_<n>.json` per size.

```bash
python run_h2_experiment.py 'SIZES=[10,20,40]' GENERATIONS=5
```

Quote the list so your shell does not eat the brackets. Cost scales with the
product of `SIZES` length and `GENERATIONS`, so a five-size sweep at 10
generations is 50 model calls, not 10.

`run_h2_experiment.py` reads no `ELITISM_INTERVAL`. Setting one does nothing.

## Reading the output

Both scripts append to `experiment_log.json`, one entry per generation:

```python
import json

with open("experiment_log.json") as f:
    log = json.load(f)

improved = sum(
    1
    for e in log
    if e["parent_cost"] is not None and e["child_cost"] < e["parent_cost"]
)
print(f"{improved}/{len(log)} generations beat their parent")
```

`analyze_results.py` plots the same log several ways:

```bash
python analyze_results.py
```

It provides `plot_multiple_views()`, `plot_simple_trend()`,
`plot_metric_over_generations()`, and `compare_rl_vs_llm()`. Import them if you
want one view rather than all of them.

## Where the files actually land

Hydra changes the working directory before the script runs, so results go to
`outputs/<date>/<time>/`, **not** the project root — including a fresh, empty
`cadence_db.sqlite` for every run. To keep everything in one place:

```bash
python run_h1_experiment.py hydra.run.dir=.
```

This is the single most common source of "where did my results go?" and
"why is the dashboard empty?". See
[Configuration](configuration.md#where-output-goes-and-the-gotcha).

## Resuming

Both scripts read `experiment_log.json` on startup and skip generations
already in it. Interrupting a run and restarting continues rather than
repeating — which matters, because repeating means paying again.

`main.py` behaves the same way, unless `FORCE_RERUN=true`, which deletes the
log first.

## Before you trust a result

An evolution run is a stochastic search driven by a non-deterministic model.
One run is an anecdote.

- **Vary the seed set.** A program tuned on `[1,2,3,4,5]` may be tuned to
  those five instances rather than to the problem.
- **Repeat the run.** Two runs of the same config will not agree. Report a
  spread, not a single best number.
- **Compare against spend.** Sixty generations beating thirty is not a
  finding; it is sixty generations. Cost per unit of improvement is the
  comparable figure, and nothing in the repository records it for you yet.
- **Read the winning program.** The fastest way to find out that your scoring
  function rewards something you did not intend.

## The prompt-strategy experiment

`experiments/` holds a separate, self-contained comparison of prompting
strategies, with its own config and analysis:

```bash
python experiments/run_experiment.py
```

`experiments/experiment_config.py` provides `validate_config()`,
`save_config()`, and `load_config()`. Results analysis lives in
`experiments/experiment_analysis.py`.

## See also

- [Configuration](configuration.md) — every key each script reads
- [Visualising results](results-visualization.md) — plotting the database
- [Evolution pipeline](evolution.md) — what one generation does
