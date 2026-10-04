# Knapsack lab

The lab evolves a small knapsack heuristic using scripted responses. It is the safest first example when you want to inspect the lifecycle without a provider key.

## Run it

From the repository root:

```bash
uv run python examples/lab/demo.py
```

The project contains:

```text
examples/lab/
├── .cadence
├── IMPROVE.md
├── demo.py
├── items.py
└── pack.py
```

`pack.py` contains the editable region. `demo.py` drives the scripted provider and prints the resulting report.

## What to watch

The first response improves the score. Later responses are malformed on purpose. Cadence records those proposals as unusable or rejected instead of treating them as successful candidates.

This example is not evidence that a particular model or prompt strategy is generally effective. It demonstrates the boundaries and failure handling of the runner.
