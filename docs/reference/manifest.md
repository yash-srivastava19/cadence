# Manifest reference

The `.cadence` file declares the experiment. The current format is `cadence/v1alpha2`.

```yaml
api_version: cadence/v1alpha2
program: solve.py
run: python {program}
metrics:
  score: maximize
experiment: my-question
guidance: IMPROVE.md
markers:
  begin: "CADENCE:BEGIN"
  end: "CADENCE:END"
method:
  evolution: {size: 8, tournament: 3}
pick:
  confirm: {seeds: [100, 101], top: 3}
objective:
  weighted_sum: {score: 1.0}
model:
  gemini: {}
prompt:
  template: region
  hints: [try a different strategy entirely]
budget:
  trials: 20
  usd: 5.0
sandbox:
  seconds: 10
  memory_mb: 256
  seeds: [0, 1, 2]
verifier:
  tolerance: 0.0
```

Run `cadence schema` for the machine-readable schema used by editors and validation tools.

## Required fields

| Field | Meaning |
| --- | --- |
| `api_version` | Manifest format version. |
| `program` | File containing the editable region. |
| `run` | Scoring command. `{program}` is replaced with the candidate path. |
| `metrics` | Metric names mapped to `maximize` or `minimize`. |
| `model` | Provider configuration. |
| `budget.trials` | Maximum number of trials. |

## Execution fields

| Field | Meaning |
| --- | --- |
| `sandbox.seconds` | Wall-clock limit for one scoring command. |
| `sandbox.memory_mb` | Memory limit for one scoring command. |
| `sandbox.seeds` | Seeds used to measure each candidate. |
| `verifier.tolerance` | Declares the numeric repeatability tolerance for cached verdicts. |

## Choosing the winner

`method` chooses which program to improve next. `pick` chooses which program the run reports as its winner. That is the program `cadence apply` writes.

| `pick` | What it does |
| --- | --- |
| unset | Reports the method's best program. |
| `best` | Same as unset. |
| `confirm: {seeds, top}` | Scores the `top` best programs (default 3) again on `seeds`, and reports the one that scores best there. |

Use `confirm` when the score is noisy. The best of many noisy scores is partly luck, so scoring the leaders again on new seeds gives a winner you can trust more. Use seeds that are not in `sandbox.seeds`.

With `confirm`:

- The reported metrics are the new scores. The `evidence` field shows the seeds and what the winner scored during the search.
- Scoring again is not a trial, and it does not count against `budget.trials`.
- If none of the leaders scores on the new seeds, the run reports the method's best and says why in `evidence.unconfirmed`.

## Provider fields

Supported provider names are `scripted`, `gemini`, `openai`, `anthropic`, and `ollama`. Provider keys come from the environment. See [Environment](environment.md).

## Configuration precedence

Cadence reads `.env` in the project directory. Variables already present in the environment take precedence. Provider-specific local configuration belongs in `providers.local.yml`, which is gitignored.
