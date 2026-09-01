# Cadence

[![CI](https://github.com/yash-srivastava19/cadence/actions/workflows/python-ci.yml/badge.svg)](https://github.com/yash-srivastava19/cadence/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Cadence is a system for evolving code that you can measure.**

You bring a program, a scoring command, and a sandbox. Cadence brings the loop: propose a change, apply it as a diff, measure the candidate in your environment, keep what improved, and iterate from the best evidence so far.

## When to Use Cadence

Cadence is for problems where:
- You can express “better” as a metric (latency, accuracy, throughput, a custom score)
- The problem lives in code (a heuristic, a parser, a model-serving path, a routing policy)
- You want the search to stay inside *your* sandbox with *your* data and *your* secrets

**Not for:** benchmarks that compare models, generic code generation, problems without a measurable objective, or one-off rewrites.

## The Design Philosophy

The core constraint: your problem stays yours.

Cadence connects through narrow interfaces. Your files, verifier, data, secrets, sandbox policy, and model backend are external. The core loop never reaches out and touches them. This matters because it means:
- A new search method doesn't need to know how you run code
- A new sandbox doesn't need to care how the model was chosen
- A new reporting surface doesn't need to touch the search algorithm
- You can swap backends, metrics, or search strategies without rewriting the coordinator

```text
              propose        apply         measure        select
program  ──▶  model  ──▶  unified diff ──▶ sandbox ──▶ objective ──▶ next
              ▲                           │
              │                           ▼
          backend                    metrics on stdout
```

## Quickstart

The repository includes a small knapsack lab that runs with a scripted model—no API key needed.

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
uv sync
uv run cadence check examples/lab
```

`cadence check` validates your setup. It reads `.cadence`, finds the editable region, runs the baseline once, and confirms the metric can be read.

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

The first candidate improves the score. Later scripted replies are intentionally malformed so you can see Cadence retry the model, reject unusable output, and continue instead of collapsing.

## Run Your Own Project

A Cadence project needs three things: a marked program, a scoring command, and a manifest. This minimal example fits in one file so you can paste it into an empty directory and validate the setup before bringing Cadence to a larger codebase.

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

Cadence only rewrites the marked region. Everything else stays fixed.

Save as `pack.py`.

### Expose Metrics

Cadence reads numbers from stdout. JSON is cleanest:

```python
import json
print(json.dumps({"value": 45, "weight": 18}))
```

Plain lines work too: `value: 45` or `value = 45`.

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

With the starter implementation, `cadence check` should report `value = 0`. That is the baseline Cadence will try to beat once you configure a model backend.

For real projects, keep the evolved file separate from the verifier:

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

Cadence copies your project to a workspace, writes the candidate over `pack.py`, and runs `python verify.py`. You can also run the verifier by hand.

## Configure Models

Backends are configured in `.cadence`. Keys come from environment variables, so the manifest can stay committed:

```yaml
model:
  openai:
    model: your-model-name
```

Providers are defined in `cadence/control/backends/providers.yml`. Adding a new one is just YAML.

Then start the run:

```bash
uv run cadence run .
```

## Tune The Experiment

Product decisions live in the manifest:

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

`IMPROVE.md` tells the model about your project: constraints, known gotchas, ideas to try.

Check the schema:

```bash
uv run cadence schema
```

## Architecture: Designed for Extension

Cadence is split into three product planes and a small shared vocabulary. Each plane can be swapped without touching the others.

```text
cadence/
  core/          DTOs, verdicts, identities, and ports
  lifecycle/     state-machine support
  observe/       run signals
  parsing/       metric reading

  control/       choose parents, call models, parse replies, apply patches
  execution/     run candidates in sandboxes and return verdicts
  delivery/      present runs: CLI today, dashboards next
  commands/      check, run, schema
```

**The developer contract:**

| Plane | Owns | Doesn't Know |
| --- | --- | --- |
| `control` | search, prompts, model calls, patches, objectives | subprocess details, UI |
| `execution` | sandboxes, resource limits, verdicts, metric collection | why a candidate was chosen |
| `delivery` | reports, streams, dashboards, notebooks | how search or sandboxing works |

**Why this matters:**
- Want a new search method? Implement the `Method` interface. The coordinator and execution layer don't care.
- Want a different sandbox? Satisfy the `Executor` port. Control and delivery stay the same.
- Want a dashboard? Subscribe to run signals. You don't reach into the experiment loop.

This separation lets Cadence be both a usable tool *and* a research platform. You can use it as-is, or fork your own search strategy, sandbox, or UI without rewriting the coordinator.

## What Makes Results Trustworthy

Cadence separates concerns so results are reproducible:

- **Verdict:** whether a candidate scored, crashed, timed out, or ran out of memory. These are facts, not just bad numbers.
- **Objective:** how to rank metrics. Pareto, weighted sum, custom rules—your choice.
- **Proposal:** every model response becomes a diff. One shape for storage, review, replay, reporting.
- **Directive:** search picks a parent; prompting decides how to ask for improvement. Two separate knobs.
- **Signals:** delivery can observe a run without reaching into the search loop.
- **Manifest hash:** every result is tied to its exact configuration.

The roadmap includes model-call replay, candidate lineage, resumable runs, and live visualization of the evolution tree.

## Development

Set up the repo:

```bash
uv sync --group dev
uv run pytest
uv run pre-commit run --all-files
```

## License

MIT. See [LICENSE](LICENSE).
