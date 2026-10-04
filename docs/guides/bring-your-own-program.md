# Bring your own program

Use Cadence when you have a program whose behavior can be measured and a bounded region that is safe to rewrite.

## Mark the editable region

Put `CADENCE:BEGIN` and `CADENCE:END` around the body or expression that should change:

```python
def pack(items: list[int], capacity: int) -> list[list[int]]:
    # CADENCE:BEGIN
    return []
    # CADENCE:END
```

Everything outside the region remains fixed during a trial. The markers can be changed in the manifest when another language uses a different comment syntax:

```yaml
markers:
  begin: "CADENCE:BEGIN"
  end: "CADENCE:END"
```

## Keep the interface stable

Keep the function or entry-point signature outside the region when possible. The scorer and the candidate then agree on the same interface across every trial.

## Write a scoring command

The command in `run` is executed against a temporary copy containing the candidate. It must:

- Exit successfully when it can measure the candidate.
- Print values whose names match `metrics`.
- Return a poor metric for a valid but poor answer.
- Make verifier failures distinguishable from poor candidates.
- Avoid reading secrets from the environment.

The candidate receives `CADENCE_SEED` for each declared seed. Use it to generate deterministic inputs when your problem supports that.

## Add guidance

`IMPROVE.md` is sent with every prompt. Use it for constraints, domain facts, and ideas worth trying:

```markdown
# Improve this heuristic

Items are integers from 20 to 100. Capacity is 150.
An item never moves after placement.
Do not change the function signature or read files outside the project.
Prefer rules that leave useful capacity for later items.
```

Do not use guidance to hide constraints from your own experiment. It is part of the recorded setup and should describe the problem honestly.

## Run preflight

```bash
cadence check
```

Keep fixing the project until it says `ready`. See [Design a scorer](design-a-scorer.md) when the baseline or repeatability checks fail.
