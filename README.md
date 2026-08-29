# Cadence

[![CI](https://github.com/yash-srivastava19/cadence/actions/workflows/python-ci.yml/badge.svg)](https://github.com/yash-srivastava19/cadence/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Cadence is a laboratory for improving programs with models.

You bring a program, a scoring command, and the environment where the program
is allowed to run. Cadence brings the loop: propose a change, apply it as a
diff, execute the candidate in a sandbox, read the metrics, keep what improved,
and make the next generation from the best evidence so far.

The goal is not another benchmark harness. The goal is a system you can point
at your own problems: a packing heuristic, a parser, a trading rule, a routing
policy, a simulator, a model-serving path, or any piece of code where “better”
can be measured.

```text
              propose        apply         measure        select
program  ──▶  model  ──▶  unified diff ──▶ sandbox ──▶ objective ──▶ next
              ▲                           │
              │                           ▼
          backend                    metrics on stdout
```

Cadence is built around one constraint: your problem stays yours. Your files,
your verifier, your data, your secrets, your sandbox policy, and your model
backend are outside the core loop and connected through narrow interfaces.

## How Cadence Works

A Cadence run should feel like this:

1. Mark the part of a file the model may change.
2. Write a command that scores the current program.
3. Describe the run in `.cadence`.
4. Check the project before spending model calls.
5. Run generations.
6. Watch candidates, diffs, metrics, failures, and lineage as they happen.
7. Keep the program that actually scored better in your environment.

The research question underneath is how to make that loop reliable enough to
trust: failures have names, model calls are replayable, candidates are measured
under explicit limits, and every boundary is shaped so new search methods,
objectives, sandboxes, providers, and delivery surfaces can be added without
rewriting the coordinator.

## Quickstart

The repository includes a small knapsack lab. It runs with a scripted model, so
you can try the loop without an API key or network.

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
uv sync
uv run cadence check examples/lab
```

`cadence check` is the preflight. It reads `.cadence`, finds the editable
region, builds the search method and objective, runs the baseline once in the
sandbox, and confirms the metric can be read.

```text
  manifest    cadence/v1alpha2, 9 defaults applied
  region      pack.py lines 6-11 (6 lines the model may rewrite)
  method      evolution built with size=8, tournament=3
  objective   weighted_sum over value to maximize
  baseline    `python pack.py` exited 0 in 15ms
  metric      value = 0, and maximize is better
  sandbox     3 seeds per trial, 10s and 256MB each
  guidance    IMPROVE.md will be sent with every prompt

ready. `cadence run` will spend up to 2 trials.
```

Then run the demo:

```bash
uv run python examples/lab/demo.py
```

The first candidate improves the score. Later scripted replies are malformed on
purpose, so you can see Cadence retry the model, reject unusable output, and
continue the run instead of collapsing around one bad response.

## Run Your Own Project

A project needs a marked program, a scoring command, and a manifest. This
example is intentionally one file so you can paste it into an empty directory
and check the setup before bringing Cadence to a larger codebase.

### Create A Program

```python
ITEMS = [
    {"name": "map", "weight": 9, "value": 150},
    {"name": "compass", "weight": 13, "value": 35},
    {"name": "water", "weight": 153, "value": 200},
    {"name": "sandwich", "weight": 50, "value": 160},
    {"name": "glucose", "weight": 15, "value": 60},
    {"name": "tin", "weight": 68, "value": 45},
]
CAPACITY = 100

# CADENCE:BEGIN
def pack():
    return []
# CADENCE:END

chosen = pack()
weight = sum(ITEMS[i]["weight"] for i in chosen)
value = sum(ITEMS[i]["value"] for i in chosen) if weight <= CAPACITY else 0
print(f"value: {value}")
print(f"weight: {weight}")
```

Cadence rewrites only the region between the markers. Everything outside that
region is context for the model and fixed code for the candidate.

Save that as `pack.py`.

### Expose Metrics

Cadence reads numbers from stdout. JSON is the cleanest contract:

```python
import json

print(json.dumps({"value": 45, "weight": 18}))
```

For quick experiments, plain lines such as `value: 45` or `value = 45` also
work. The metric names are the names you put in `.cadence`.

The one-file example above uses the simple line format so there is nothing else
to install or import.

### Add A Manifest

```yaml
api_version: cadence/v1alpha2
program: pack.py
metrics:
  value: maximize
budget:
  trials: 20
```

Then:

```bash
uv run cadence check .
```

With the starter implementation, `cadence check` should report `value = 0`.
That is the baseline Cadence will try to beat once you choose a model backend.

For most real projects, keep the evolved file and the verifier separate:

```yaml
api_version: cadence/v1alpha2
program: pack.py
run: python verify.py
metrics:
  value: maximize
  weight: minimize
sandbox:
  seconds: 30
  memory_mb: 1024
  seeds: [0, 1, 2, 3, 4]
```

Cadence copies the project into a scratch workspace, writes the candidate over
`pack.py`, and runs `python verify.py` inside that workspace. Your verifier
imports the candidate by its normal filename, which means the same verifier can
be run by hand when you want to inspect a result.

## Configure Models

Backends are configured from `.cadence`. Keys come from the environment, not
from the manifest, so the file can stay committed.

```yaml
model:
  openai:
    model: your-model-name
```

After a backend is configured, start the run:

```bash
uv run cadence run .
```

Provider definitions live in `cadence/control/backends/providers.yml`. The
design is deliberately boring: if a provider speaks the OpenAI chat dialect,
adding it is data, not a new class hierarchy.

## Tune The Experiment

The manifest is where ordinary product decisions belong:

```yaml
api_version: cadence/v1alpha2
program: solver.py
run: python verify.py
guidance: IMPROVE.md
metrics:
  score: maximize
  latency_ms: minimize
method:
  evolution:
    size: 12
    tournament: 4
objective:
  pareto:
    score: 1
    latency_ms: -1
budget:
  trials: 100
sandbox:
  seconds: 20
  memory_mb: 2048
  seeds: [0, 1, 2]
model:
  ollama:
    model: qwen3:4b
```

`IMPROVE.md` is for human guidance: constraints, known traps, invariants, and
ideas worth trying. It gives the model project-specific context without baking
that context into Cadence itself.

Use the schema when in doubt:

```bash
uv run cadence schema
```

## Architecture For Extension

Cadence is split into three product planes and a small shared vocabulary.

```text
cadence/
  core/          DTOs, verdicts, identities, and ports
  lifecycle/     state-machine support
  observe/       run signals
  parsing/       metric reading

  control/       choose parents, call models, parse replies, apply patches
  execution/     run candidates in sandboxes and return verdicts
  delivery/      present runs: CLI today, richer surfaces next
  commands/      check, run, schema
```

The planes are the developer promise:

| Plane | Owns | Should not know |
| --- | --- | --- |
| `control` | search, prompts, model calls, patches, objectives | subprocess details or UI concerns |
| `execution` | sandboxes, resource limits, process outcomes, metric collection | why a candidate was chosen |
| `delivery` | reports, streams, dashboards, notebooks, logs | how search or sandboxing is implemented |

That split matters because Cadence is a research project as much as a tool. A
new search method should be one implementation behind the method interface. A
new sandbox should satisfy the execution port. A dashboard, notebook, or report
view should subscribe to events instead of reaching into the experiment loop.

## Research Roadmap

Cadence is useful when the object of study is not only “did a model find a
better answer?” but “what made the loop trustworthy enough to know?”

The system keeps separate concepts separate:

| Concept | Why it exists |
| --- | --- |
| `Verdict` | A candidate can score, crash, time out, report no metric, or exhaust memory. Those are different facts, not bad numbers. |
| `Objective` | Metrics are an open map. Ranking them is a policy, not a property of stdout. |
| `Proposal` | Every model response becomes a unified diff, so storage, review, replay, and reporting all see one durable shape. |
| `Directive` | Search chooses a parent; prompting decides how to ask the model to improve it. |
| Signals | Delivery surfaces can observe a run without coupling themselves to the coordinator. |
| Manifest hash | A result is only meaningful with the exact configuration that produced it. |

The long-term direction is durable, inspectable evolution: model-call replay,
candidate lineage, verdict caching for deterministic verifiers, resumable runs,
budget reservation, leases for parallel workers, and delivery surfaces that let
you watch a generation tree form in real time.

## Development

Set up the repo:

```bash
uv sync --group dev
uv run pytest
uv run pre-commit run --all-files
```

## License

MIT. See [LICENSE](LICENSE).
