# Cadence

[![CI](https://github.com/yash-srivastava19/cadence/actions/workflows/python-ci.yml/badge.svg)](https://github.com/yash-srivastava19/cadence/actions)
[![Docs](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://cadence.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Cadence improves a program by rewriting it over and over. A language model
proposes an edit, Cadence runs the result against a scoring function you
provide, keeps what scored better, and repeats.

You supply two things: a program with the editable region marked, and a way to
score it. Cadence supplies the loop.

## Quickstart

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
uv sync
source .venv/bin/activate
export GEMINI_API_KEY="your-key-here"

python run_h1_experiment.py
```

That evolves a Traveling Salesman heuristic for 30 generations against two
hand-written baselines, then writes `h1_results.png` and
`experiment_log.json`. It costs roughly 30 Gemini calls.

The environment variable is `GEMINI_API_KEY`. A `.env` at the project root
works too — `src/llm.py` calls `load_dotenv()` on import.

> **Where did my results go?** Hydra changes the working directory before the
> script runs, so output lands in `outputs/<date>/<time>/`, including a fresh
> empty `cadence_db.sqlite`. Pass `hydra.run.dir=.` to keep everything in the
> project root.

## How one generation works

1. **Sample a parent** — from the previous generation, or, every
   `ELITISM_INTERVAL` generations, the best program found so far.
2. **Build a prompt** from the parent, its siblings, and the current lesson.
3. **Ask the model to rewrite the marked block.**
4. **Swap the block into the parent**, positionally.
5. **Score the child** on five fixed seeds, in parallel.
6. **Store it** in SQLite with its cost, its parent, and its lineage.

Every `LESSON_INTERVAL` generations Cadence asks the model what it has learned
so far and prepends that to later prompts. Every `META_PROMPT_EDIT_INTERVAL`
generations it rewrites its own instruction text.

## Using it on your own problem

Implement four members of `Task`:

```python
from src.task import Task
from src.models import EvaluationResult


class MyTask(Task):
    @property
    def function_name(self) -> str:
        return "solve"

    def generate_inputs(self, seed: int):
        ...  # deterministic for a given seed

    def evaluate(self, output, input_data) -> EvaluationResult:
        ...  # lower cost is better

    @property
    def baseline_program(self) -> str:
        return "### START_BLOCK\ndef solve(data):\n    ...\n### END_BLOCK"
```

Everything between `### START_BLOCK` and `### END_BLOCK` is what the model
rewrites. Everything outside is fixed.

**[docs/tasks.md](docs/tasks.md) is the full guide**, with a complete worked
knapsack example and the rules about cost direction, determinism, and checking
that your scoring function can tell a good program from a bad one.

## Configuration

Every setting is a [Hydra](https://hydra.cc/) key in `conf/`. Override on the
command line rather than editing files:

```bash
python run_h1_experiment.py GENERATIONS=60 LESSON_INTERVAL=3
```

There are no `CADENCE_*` environment variables and no `--generations` style
flags. [docs/configuration.md](docs/configuration.md) lists every key that
each script actually reads.

## Web interface

```bash
python ui/launch_ui.py
```

Then open <http://localhost:5000>. It reads `./cadence_db.sqlite` relative to
where you launch it, which is why it looks empty if your run wrote to a Hydra
output directory.

## What Cadence does not do yet

Stated plainly, because finding out later wastes your time:

- **One provider.** Google Gemini only, defaulting to `gemini-2.0-flash`.
- **One objective.** A single float, minimised. No Pareto, no multi-objective.
- **One operator.** Whole-block replacement. No crossover, no full rewrite.
- **No sandbox.** Candidates run via `exec()` in the same process as the loop,
  with access to your files, environment, and network. Point Cadence only at
  code you would run by hand on the same machine.
- **No timeout.** A candidate with an infinite loop hangs the run. `Evaluator`
  accepts `timeout` and `max_memory_mb` and ignores both.

## Layout

```text
conf/                  Hydra configs, one per entry script
src/                   the library that runs today
  task.py              the Task interface
  evaluator.py         execute() -- source in, cost out
  evolve.py            apply_diff() -- block replacement
  llm.py               Gemini provider and legacy helpers
  prompt_sampler.py    build() -- prompt assembly
  database.py          SQLite storage and parent sampling
  tasks/               TSPTask
cadence/               the framework replacing src/ -- not usable yet
docs/                  documentation, tested by tests/test_docs.py
ui/                    Flask dashboard
main.py                the full loop, with lessons and meta-prompting
run_h1_experiment.py   evolution against baselines
run_h2_experiment.py   scaling across problem sizes
```

## Documentation

The docs are tested. `tests/test_docs.py` compiles every Python example,
resolves every symbol they import against the source tree, checks that every
script they name exists, and fails the build on any environment variable
nothing reads. A page that drifts from the code breaks CI.

| Page | For |
| --- | --- |
| [Getting started](docs/getting-started.md) | Your first run, and what the output means |
| [Tasks](docs/tasks.md) | Your own problem |
| [Configuration](docs/configuration.md) | Every key, and what is hardcoded |
| [Evolution pipeline](docs/evolution.md) | What each generation does |
| [Examples](docs/examples.md) | Working snippets |
| [Experiments](docs/experiments.md) | Reproducing H1 and H2 |
| [API reference](docs/api/index.md) | Signatures |
| [Architecture](docs/architecture.md) | Where this is going |
| [Contributing](docs/contributing.md) | Sending a patch |

## Citation

See [CITATION.cff](CITATION.cff).

## Licence

MIT. See [LICENSE](LICENSE).
