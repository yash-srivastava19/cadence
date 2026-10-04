# Design the harness

The harness is the part of the experiment that says what “better” means. A capable model cannot rescue a scorer that measures the wrong thing.

## Five questions

Before you spend a model call, check that your problem has:

1. **Objective truth.** People can agree what a better result means.
2. **Fast verification.** A candidate can be measured in a reasonable time.
3. **Scalable verification.** You can measure many candidates with the same procedure.
4. **Low noise.** The score is meaningfully correlated with the behavior you want.
5. **A useful reward.** Results can be compared, not merely accepted or rejected.

These properties are practical design guidance, not promises that every problem will improve.

## A scorer is a measurement instrument

Suppose the thing you want is a route that is short and valid. A scorer that only counts the number of returned items can reward a route that is fast to produce but not a route that solves the problem. The model may improve that number faithfully. The experiment would still be wrong.

Write down the claim before writing the metric:

```text
claim: this program produces valid routes with lower total distance
metric: total_distance, minimized
guard: invalid routes produce a verifier failure, not a short distance
reference: baseline route measured by the same scorer
```

The metric is not the claim. It is the instrument used to gather evidence for the claim.

## Keep the scorer outside the region

```python title="solve.py"
def choose(items):
    # CADENCE:BEGIN
    return items[0]
    # CADENCE:END
```

```python title="score.py"
# This command is outside the editable region.
from solve import choose

print(f"score: {measure(choose, cases)}")
```

If the candidate can rewrite its own scorer, the experiment no longer measures a stable objective.

## A small complete scorer

This example keeps the candidate and the measurement visibly separate:

```python title="score.py"
import json
import os

from solve import choose


def main() -> None:
    seed = int(os.environ["CADENCE_SEED"])
    items = make_case(seed)
    answer = choose(items)
    if answer not in items:
        raise SystemExit("verifier_error: candidate returned an unknown item")
    print(json.dumps({"score": value_of(answer, items)}))


if __name__ == "__main__":
    main()
```

The candidate can be inventive inside `choose`. It cannot change `make_case`, `value_of`, or the validity guard because those live in the scorer.

<details>
<summary>Why not turn invalid output into a very bad score?</summary>

Sometimes that is the right choice. If invalid output still gives you a meaningful, comparable measurement, return a deliberately poor score. Use a verifier failure when the scorer cannot establish what the score would mean. The important rule is to choose deliberately and document the distinction.

</details>

## Separate bad results from broken measurements

Make a wrong answer score badly when possible. Reserve a verifier error for a scorer that could not establish a result. A candidate that crashes is different from a candidate that returns a valid but poor answer.

!!! warning "The measurement can lie"
    A run can improve its declared validation score while getting worse on a held-out distribution. Compare the training, validation, and held-out behavior before treating a winner as a discovery.

## Make `check` part of the workflow

`cadence check` is the preflight for the experiment. It runs the baseline, checks that metrics are reported, checks repeatability when configured, and reports the limits and budget. Treat a non-ready result as a harness bug, not as a prompt problem.

## A useful preflight question

Before running, ask:

> If the number improves, what exactly will I believe happened?

If the answer is unclear, the next change belongs in the harness, not in the prompt.
