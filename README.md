# Cadence

[![CI](https://github.com/yash-srivastava19/cadence/actions/workflows/python-ci.yml/badge.svg)](https://github.com/yash-srivastava19/cadence/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> [!WARNING]
> Cadence is alpha. The manifest format is versioned (`cadence/v1alpha2`), and
> older versions are converted when read, but expect breaking changes before
> a stable release.

**Evolve code you can measure. Mark the part of a program a model may rewrite, name the command that scores it, and Cadence searches for a better version inside your sandbox.**

```python
# solve.py -- only the marked region is ever rewritten
# CADENCE:BEGIN
def solve(problem: list[int]) -> int:
    return sum(problem)
# CADENCE:END
```

```yaml
# .cadence
api_version: cadence/v1alpha2
program: solve.py        # the file with the marked region
run: python score.py     # scores a candidate; prints `score: <number>`
metrics:
  score: maximize
budget:
  trials: 20
model:
  gemini: {}
```

```bash
cadence check     # what will run, how it is scored, what it will cost; spends nothing
cadence run       # propose, measure, keep what improved, repeat
```

Why it exists, and what happened when it was pointed at problems with
published answers: [The Harness Was the Experiment](https://yash-sri.xyz/blog/evolving_problems_cadence).

## The idea

Every trial goes around the same loop:

```text
            propose          apply           measure          select
program ──▶  model  ──▶  unified diff ──▶  your command ──▶  objective ──▶ next parent
```

You bring three things, and Cadence never reaches past them:

| You bring | What it is | Why it is separate |
|---|---|---|
| **A marked program** | The file, with `CADENCE:BEGIN` / `CADENCE:END` around the part that may change | Everything outside the markers stays fixed, so every trial is comparable |
| **A scoring command** | Anything that runs a candidate and prints numbers | It lives outside the region, so a candidate cannot set its own score |
| **A manifest** | `.cadence`: metrics, budget, model, sandbox limits | One file states the whole experiment, and its hash is recorded with every result |

What comes back from each trial is a **verdict**, not just a number. A
candidate that crashed, timed out, ran out of memory, or printed no metric is
recorded as that, with the reason. A score is a score, and a failure is never
a zero.

## Why?

| You want to... | Cadence gives you |
|---|---|
| Know what a run will do before paying for it | `cadence check`: the region, the baseline score, whether it repeats, the sandbox, the cost |
| Keep the model away from how it is judged | The region markers, and a scoring command outside them |
| Run candidates with limits | A sandbox per trial: wall clock, memory, output size, a clean environment |
| Use your own model, or a hosted one | Gemini, OpenAI, Anthropic or Ollama, set in `.cadence`. The key comes from the environment, never from a file |
| See what happened, step by step | A JSON log of every step in `cadence-runs/`, with or without a database |
| Stop today and carry on tomorrow | Recorded runs resume from the database, and calls already paid for are replayed, not repeated |
| Keep the winner | `cadence apply` writes a run's best program over yours |

## Quick start

### 1. Install

```bash
uv tool install git+https://github.com/yash-srivastava19/cadence
```

This puts `cadence` on your `PATH`, so it works from any directory. It needs
[uv](https://docs.astral.sh/uv/). If your system Python is newer than
Cadence supports, uv fetches a compatible one.

To keep runs in a database (step 6), you will also need a clone of this
repository. The database migrations live there.

### 2. Start a project

In an empty directory:

```bash
cadence init
```

```text
  wrote       .cadence
  wrote       solve.py
  wrote       score.py
  wrote       IMPROVE.md

Now run `cadence check .`.
```

| File | What it is |
|---|---|
| `solve.py` | The program. Only the code between the markers changes |
| `score.py` | Runs `solve` and prints `score: <number>`. The model never sees it as editable |
| `.cadence` | The manifest |
| `IMPROVE.md` | Sent with every prompt: what the code does, what may change, what may not |

To use Cadence on your own code, replace `solve.py`'s marked region with
yours and make `score.py` measure it. See [Bring your own program](#bring-your-own-program).

### 3. Choose a model

`init` writes `model: {gemini: {}}`. Set its key in the environment:

```bash
export GEMINI_API_KEY=...        # or GOOGLE_API_KEY
```

To keep everything on your machine, use [Ollama](https://ollama.com) instead:

```yaml
model:
  ollama:
    model: <a model you have pulled>
```

See [Models](#models) for the others.

### 4. Check

```bash
cadence check
```

```text
  manifest    cadence/v1alpha2, 7 defaults applied
  region      solve.py lines 9-17 (9 lines the model may rewrite)
  scoring     reported from outside the region
  method      evolution built with size=8, tournament=3
  model       gemini, model gemini-3.6-flash
  objective   weighted_sum over score to maximize
  baseline    `python score.py` exited 0 in 25ms
  metric      score = 31, and maximize is better
  sandbox     3 seeds per trial, 10s and 256MB each
  repeatable  scored the same twice, and nothing declares it -- set verifier.tolerance to let cadence reuse a score
  cost        20 trials x 3 seeds x 25ms is about 1s of scoring
  guidance    IMPROVE.md will be sent with every prompt
  recording   nothing will be recorded -- DATABASE_URL is not set

ready. `cadence run` will spend up to 20 trials.
```

`check` runs your baseline once and calls no model. If something would stop a
run, like a missing key or a metric that is never printed, it says so and
does not say `ready`.

### 5. Run

```bash
cadence run
```

Progress goes to stderr, one line per trial. The result goes to stdout: the
best program, its metrics, and what the run spent. Pipe it (`cadence run >
result.json`) or read it on the terminal.

Without a database, that output is the only copy of the winner. Keep it, or
set up recording first.

Every run also writes a log of each step to `cadence-runs/`, with or without
a database. See [Logs](#logs).

### 6. Keep runs, resume them, apply the winner

Recording needs Postgres and the migrations from this repository:

```bash
git clone https://github.com/yash-srivastava19/cadence && cd cadence
docker compose up -d                                  # Postgres on localhost:5433
export DATABASE_URL=postgresql://cadence:cadence@localhost:5433/cadence
uv run alembic upgrade head                           # once per database
```

Then, from your project, with `DATABASE_URL` still set:

```bash
cadence check                    # now says the run will be recorded
cadence run                      # prints a run id
cadence runs list                # every recorded run, newest first
cadence trials list --run RUN_ID # the trials of one run
cadence run --resume RUN_ID      # carry on a run that stopped
cadence apply RUN_ID             # write the best program over yours
```

`apply` overwrites your program and keeps no backup. Commit first.

Cadence also reads a `.env` file in the current directory. Variables that
are already set in the environment take precedence.

## Bring your own program

**Mark the region.** Put the markers around the *body* of what should
change, and keep the signature the rest of the program calls:

```python
def pack(items, capacity):
    # CADENCE:BEGIN
    return []
    # CADENCE:END
```

**Print the metrics.** The scoring command prints numbers on stdout, with
names that match `metrics:` in `.cadence`. Any of these is read:

```text
{"value": 45, "weight": 18}
value: 45
value = 45
```

**Score outside the region.** If the region prints its own score, the model
can rewrite that line. `check` warns when it sees this.

**Make a wrong answer score badly, not crash.** A crash tells the run the
code is broken. A low score tells it the answer was poor. They are different
lessons.

**Tell the model what matters** in `IMPROVE.md`: constraints, what may not
change, and ideas worth trying.

Then run `cadence check` until it says `ready`.

## The manifest

`init` writes the short form. Every field, with its default where it has one:

```yaml
api_version: cadence/v1alpha2
program: solve.py            # the file with the marked region
run: python {program}        # the scoring command; {program} is replaced
metrics:                     # required: name -> maximize | minimize
  score: maximize
experiment: my-question      # unset by default; groups runs in a shared database
guidance: IMPROVE.md         # sent with every prompt
markers:
  begin: "CADENCE:BEGIN"
  end: "CADENCE:END"
method:                      # how the next parent is chosen
  evolution: {size: 8, tournament: 3}
objective:                   # unset by default: a weighted sum over metrics
  weighted_sum: {score: 1.0}
model:                       # scripted | gemini | openai | anthropic | ollama
  gemini: {}
prompt:
  template: region           # region | rewrite | improve
budget:
  trials: 20
  usd: 5.0                   # unset by default; enforced only where a price is declared
sandbox:
  seconds: 10                # wall clock per run of the scoring command
  memory_mb: 256
  seeds: [0, 1, 2]           # each trial is scored once per seed
verifier:
  tolerance: 0.0             # unset by default; declares the score repeatable, so it can be reused
```

`cadence schema` prints the JSON Schema. Point your editor at it for
completion and validation.

Each trial copies the project into a temporary directory, writes the
candidate over `program`, and runs `run` there with the seed in
`CADENCE_SEED`. The command gets a clean environment: your keys are not
passed to it.

## Models

| Name | Key from | Notes |
|---|---|---|
| `gemini` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Default model `gemini-3.6-flash` |
| `openai` | `OPENAI_API_KEY` | Name a model: `openai: {model: ...}` |
| `anthropic` | `ANTHROPIC_API_KEY` | Name a model: `anthropic: {model: ...}` |
| `ollama` | none | Local. `OLLAMA_HOST` overrides the address |
| `scripted` | none | Canned answers, for tests. It cannot run from the CLI |

Providers are defined in
[`providers.yml`](cadence/control/backends/providers.yml). Every provider
speaks the OpenAI dialect, so adding one is a row. Put prices and local
overrides in `providers.local.yml`, which is gitignored. With a price
declared, a run reports what it cost.

## Everyday commands

```bash
cadence init [DIR]                   # write a project that check already passes
cadence check [DIR]                  # everything about a run, without running it
cadence run [DIR]                    # run the search
cadence run --config FILE            # use FILE instead of DIR/.cadence
cadence run --resume RUN_ID          # carry on a recorded run
cadence runs list                    # recorded runs
cadence runs show RUN_ID             # one run in full
cadence trials list --run RUN_ID     # the trials of a run
cadence trials show TRIAL_ID         # one trial in full
cadence apply RUN_ID [DIR]           # write the winner over your program
cadence schema                       # the manifest's JSON Schema
```

`check`, `run`, `runs` and `trials` take `--json`. It is the default when
output is not a terminal.

## Logs

Every `cadence run` writes one file, one JSON object per line, one line per
step:

```text
cadence-runs/
├── .gitignore            # "*": the folder ignores itself, so logs are never committed
└── development/          # the environment, from CADENCE_ENV (default: development)
    └── <run-id>.jsonl
```

The run prints the path when it ends. A line looks like this:

```json
{"ts":"2026-09-21T12:50:41.380Z","level":"info","run":"20260921-124926-4dfc96","trial":"20260921-124926-4dfc96/0","span":"model_call","phase":"end","status":"ok","message":"model replied: gemma3:4b, 850 in / 49 out, 74.3s","id":"20260921-124926-4dfc96/0/call-1","parent":"20260921-124926-4dfc96/0","trace_id":"…","span_id":"…","parent_span_id":"…","duration_ms":74341.1,"attrs":{"tokens_in":850,"tokens_out":49,"response_hash":"00c824a847b25b65"}}
```

| Field | What it is |
|---|---|
| `level` | `info`; `warn` when something cost a call and bought nothing (an unusable reply, a rejected patch); `error` when the run cannot go on |
| `span` | The step: `run`, `baseline`, `trial`, `model_call`, `read_reply`, `apply_patch` or `measure` |
| `phase` | `start` and `end` of a step, or `event` for a single moment |
| `status` | How the step ended: `ok`, `scored`, `failed:crashed`, `unusable`, `abandoned`… |
| `message` | The line as a sentence |
| `trace_id`, `span_id`, `parent_span_id` | OTEL-shaped IDs: one trace per trial, one span per step. They're derived from the run and trial IDs, so they stay the same across a resume |
| `attrs` | The step's own numbers and identifiers |

Your code, the model's replies and the prompts are never written to the
log, only their hashes. The text of a crash (the last lines of stderr) is
kept, because the file stays on your machine.

```bash
L=$(ls -t cadence-runs/development/*.jsonl | head -1)

jq -r '.message' $L                                     # the run as sentences
tail -f $L | jq .                                       # follow a run live
grep '"level":"warn"' $L                                # what cost something and bought nothing
jq -r 'select(.span=="trial" and .phase=="end") | "\(.trial) \(.status) \(.duration_ms)ms"' $L
jq -s 'map(select(.span=="model_call" and .phase=="end")) | map(.attrs.tokens_in + .attrs.tokens_out) | add' $L
```

To keep runs from different setups apart, set the environment:
`CADENCE_ENV=staging cadence run` writes to `cadence-runs/staging/`.

## Try it without a key

The repository includes a small knapsack lab and a script that drives it
with canned model answers:

```bash
git clone https://github.com/yash-srivastava19/cadence && cd cadence
uv run python examples/lab/demo.py
```

The first answer improves the score. The later ones are malformed on
purpose, so you can watch Cadence retry the model, reject what it cannot
use, and carry on.

## Known rough edges

- Reasoning models served through Ollama's OpenAI endpoint can return an
  empty reply, because the answer arrives in a separate reasoning field.
- A model that repeats the `CADENCE:BEGIN` / `CADENCE:END` lines in its
  answer ends the run instead of failing one trial.
- The sandbox limits time, memory and output, and passes a clean
  environment. It does not restrict network access, or files outside the
  working copy. Run it where that is acceptable.

## Architecture

The design, and why it is shaped this way: [Cadence](https://yash-sri.xyz/blog/cadence_blog).

```text
cadence/
  core/        DTOs, verdicts, identities, ports
  lifecycle/   state machines
  observe/     run signals
  parsing/     metric reading
  control/     choose parents, call models, parse replies, apply patches, record
  execution/   run candidates in a sandbox and return what happened
  delivery/    how results are presented
  commands/    the CLI
```

| Plane | Owns | Does not know |
|---|---|---|
| `control` | search, prompts, model calls, patches, objectives, the record | how a candidate is run |
| `execution` | sandboxes, limits, verdicts, metric collection | why a candidate was chosen |
| `delivery` | how results are shown | how search or sandboxing works |

The layers are enforced by `import-linter` in CI. To add a search method,
implement the `Method` port. To add a sandbox, implement `Sandbox`. To watch
a run, subscribe to its signals.

## Development

```bash
git clone https://github.com/yash-srivastava19/cadence && cd cadence
make install      # uv sync with the dev and test tools
make test         # pytest; the database tests need TEST_DATABASE_URL
make lint         # mypy, ruff, import-linter
make fmt
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
