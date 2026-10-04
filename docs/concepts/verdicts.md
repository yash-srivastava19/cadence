# Verdicts, not numbers

Cadence records what happened when a candidate was measured. A verdict is either a score that can be ranked or a reason the measurement did not produce one.

## Scored outcomes

A scored verdict contains the declared metrics. The objective uses those metrics in the direction declared by the manifest:

```yaml
metrics:
  error: minimize
  throughput: maximize
```

## Failed outcomes

Failure outcomes include the reason instead of pretending that failure is a numeric result. Common cases are:

| Outcome | Meaning |
| --- | --- |
| `crashed` | The candidate or scorer exited with an error. |
| `timed_out` | The sandbox wall-clock limit was reached. |
| `out_of_memory` | The memory limit was reached. |
| `no_metric` | The scorer exited but did not report a declared metric. |
| `verifier_error` | The scorer could not establish a valid measurement. |
| `unusable` | The model response could not produce an applicable patch. |

The exact status shown in the terminal and logs is the evidence to investigate. Do not replace it with a hand-written zero in analysis code.

## Why this matters

If a crash becomes zero, a minimization objective may prefer broken candidates. If a verifier error becomes a bad score, the search may learn from a measurement failure. Keeping verdicts typed makes those errors visible.
