# Design a scorer

The scorer is the most important part of a Cadence project. It is the measuring instrument for every claim the run makes.

## Start with a baseline

Run the unmodified program against the same inputs and seeds used for candidates. Keep the baseline in the run record so later improvements have a reference point.

## Choose metric direction explicitly

```yaml
metrics:
  excess_bins: minimize
  packed_value: maximize
```

Do not make the reader infer whether a smaller or larger number is better.

## Use the right data split

If the problem can overfit, maintain separate data for:

- Training or search inputs.
- Validation inputs used by the objective.
- Held-out inputs used only after the run.

An improvement on validation is not evidence of generalization when the held-out distribution changes.

## Make repeatability visible

Use fixed seeds for deterministic problems. If a scorer is repeatable within a known tolerance, declare it so the verdict cache can reuse a measurement:

```yaml
verifier:
  tolerance: 0.01
```

Do not declare a tolerance simply to make a run faster. It changes what Cadence considers the same measurement.

## Bound the execution

```yaml
sandbox:
  seconds: 60
  memory_mb: 512
  seeds: [0, 1, 2]
```

The sandbox limits wall time, memory, output, and the environment passed to the scoring command. It does not currently restrict network access or files outside the working copy. Run untrusted projects only where that boundary is acceptable.

## Test failure modes yourself

Before using a model budget, deliberately test:

- A candidate that returns a poor answer.
- A candidate that crashes.
- A scorer that prints no metric.
- A scorer that cannot verify its input.
- A candidate that exceeds the time limit.

The result should tell you which case occurred. A failure must not silently become a score.
