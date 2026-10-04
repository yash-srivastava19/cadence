# Architecture

Cadence separates the decision to propose a candidate from the ability to execute and measure it. The result is a system where the terminal, dashboard, database, and logs can describe the same run without each implementing its own interpretation.

```text
commands / web
       ↓
delivery
       ↓
control
       ↓
execution
       ↓
scoring command in a sandbox
```

## The durable record

Runs, trials, candidates, model calls, verdicts, and manifests are recorded as facts. The search can be restored from those facts rather than inferred from process memory.

## Extension points

The package uses ports for the parts that vary:

- `Method` chooses the next parent or proposal strategy.
- `Model` supplies a proposal.
- `Sandbox` runs a candidate under limits.
- `Storage` records and restores the run.
- Signals publish what happened to delivery surfaces.

See [System planes](planes.md) for the ownership boundaries.
