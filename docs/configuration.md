# Configuration

Cadence has two configuration surfaces and no others: one environment
variable, and a set of [Hydra](https://hydra.cc/) keys in `conf/`.

Every key on this page is read by a script in this repository. If a setting is
not listed here, it does not exist.

## The environment variable

| Variable | Read by | Required |
| --- | --- | --- |
| `GEMINI_API_KEY` | `src/llm.py` | Yes, for any run that calls the model |

`src/llm.py` calls `load_dotenv()` when imported, so a `.env` file at the
project root works as well as an exported variable. Keep `.env` untracked; it
is already in `.gitignore`.

There is no `CADENCE_*` variable of any kind. Database path, log level,
worker count, and timeouts are not configurable by environment.

## Hydra keys

Each entry script owns one config file in `conf/` and reads a specific set of
keys. A key that a script does not read is ignored silently, so putting
`GENERATIONS` in `main_config.yaml` does nothing.

### `main.py` — `conf/main_config.yaml`

```yaml
NUM_GENERATIONS: 6
ELITISM_INTERVAL: 3
META_PROMPT_EDIT_INTERVAL: 10
LESSON_INTERVAL: 2
FORCE_RERUN: true
START_GENERATION: 0
```

| Key | Meaning |
| --- | --- |
| `NUM_GENERATIONS` | How many generations to run, counting from `START_GENERATION` |
| `ELITISM_INTERVAL` | Every N generations, breed from the best program found so far instead of sampling |
| `META_PROMPT_EDIT_INTERVAL` | Every N generations, ask the model to rewrite its own instruction text |
| `LESSON_INTERVAL` | Every N generations, extract a lesson from history and use it in later prompts |
| `FORCE_RERUN` | `true` deletes `experiment_log.json` and `lesson_history.json` and starts over. `false` resumes, skipping generations already in the log |
| `START_GENERATION` | Generation number to count from. Use it to continue a finished run |

### `run_h1_experiment.py` — `conf/h1_config.yaml`

Evolution against two fixed baselines, plotted to `h1_results.png`.

```yaml
SEEDS: 3
GENERATIONS: 30
LESSON_INTERVAL: 5
ELITISM_INTERVAL: 5
API_MAX_RETRIES: 2
API_TIMEOUT: 100
```

| Key | Meaning |
| --- | --- |
| `SEEDS` | Number of TSP instances used to score the baseline heuristics |
| `GENERATIONS` | Length of the evolution run |
| `LESSON_INTERVAL` | As above |
| `ELITISM_INTERVAL` | As above |
| `API_MAX_RETRIES` | Attempts per model call before the generation is skipped |
| `API_TIMEOUT` | Seconds to wait for one model call |

### `run_h2_experiment.py` — `conf/h2_config.yaml`

Scaling: the same evolution repeated at several problem sizes.

```yaml
SIZES: [10, 15, 20, 25, 30]
GENERATIONS: 10
SEEDS: 10
API_MAX_RETRIES: 2
API_TIMEOUT: 60
LESSON_INTERVAL: 7
```

`SIZES` is the list of city counts to sweep. The rest match the table above.
Note there is no `ELITISM_INTERVAL` here — `run_h2_experiment.py` does not
read one.

## Overriding without editing files

Hydra takes `KEY=value` arguments. This is the normal way to change a run:

```bash
python run_h1_experiment.py GENERATIONS=60 LESSON_INTERVAL=3
```

Lists use bracket syntax, quoted so the shell leaves them alone:

```bash
python run_h2_experiment.py 'SIZES=[10,20,40]' GENERATIONS=5
```

To use a different config file entirely:

```bash
python run_h1_experiment.py --config-name my_config
```

The file goes in `conf/`, and `--config-name` takes its name without the
`.yaml` extension.

Hydra's own flags work too — `--help` lists the resolved config, and
`--cfg job` prints it without running anything:

```bash
python run_h1_experiment.py --cfg job
```

## Settings that are not configurable

These are constants in the source. Changing them means editing the file, and
they are listed here so you stop looking for a key.

| Setting | Value | Where |
| --- | --- | --- |
| Model name | `gemini-2.0-flash` | `LLMConfig.model`, `src/llm.py` |
| Evaluation seeds | `[1, 2, 3, 4, 5]` | `execute()`, `src/evaluator.py` |
| Parallel evaluation workers | `min(len(seeds), 4)` | `execute()`, `src/evaluator.py` |
| Cost assigned to a failed program | `1e8` | `INFEASIBLE_COST`, `src/evaluator.py` |
| Feasibility threshold | more than half the seeds must pass | `execute()`, `src/evaluator.py` |
| Database path | `cadence_db.sqlite` | `DatabaseConfig.database_path`, `src/models.py` |
| Web interface port | `5000` | `ui/launch_ui.py` |

`Evaluator` accepts `timeout` and `max_memory_mb` arguments, stores them, and
never applies them. They are not a way to limit a run.

## Where output goes, and the gotcha

Hydra changes the working directory before your script runs. With the shipped
configs it creates `outputs/YYYY-MM-DD/HH-MM-SS/` and moves into it, so
**every file the run writes lands there, not in the project root** — including
a brand new, empty `cadence_db.sqlite`.

That surprises people twice. The web interface reads
`./cadence_db.sqlite` relative to where you launch it, so it shows an empty
database while a run is in progress. And a second run does not accumulate
history with the first.

To keep everything in the project root instead:

```bash
python run_h1_experiment.py hydra.run.dir=.
```

Or make it permanent by adding this to the config file:

```yaml
hydra:
  run:
    dir: .
  output:
    subdir: null
```

| File | Written by |
| --- | --- |
| `experiment_log.json` | every generation of any entry script |
| `lesson_history.json` | the lesson extractor |
| `cadence_db.sqlite` | `src/database.py`, on every program added |
| `h1_results.png` | `run_h1_experiment.py` |
| `h2_log_size_<n>.json` | `run_h2_experiment.py`, one per size in `SIZES` |

Log formatting comes from `conf/hydra/job_logging/custom.yaml`, which routes
everything through `rich.logging.RichHandler` at `INFO`.
