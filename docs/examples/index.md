# Examples

The repository includes runnable examples that show different kinds of Cadence problems.

| Example | What it demonstrates |
| --- | --- |
| [Knapsack lab](knapsack.md) | A complete offline run with scripted model responses. |
| `examples/cache` | A policy function, workload, and manifest for a real project shape. |

Run the lab without a provider key:

```bash
uv run python examples/lab/demo.py
```

The lab deliberately includes malformed later answers so you can see Cadence reject an unusable proposal and continue. It is a good example for agents and documentation tests because it spends no network budget.
