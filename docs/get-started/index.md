# Get started

Run a complete Cadence project without setting up a database. You will create a marked program, configure a scoring command, inspect the plan with `cadence check`, and run a bounded search.

## Prerequisites

- Python 3.11, 3.12, or 3.13.
- [uv](https://docs.astral.sh/uv/).
- A model provider key, unless you use the repository's scripted lab.

## Install the CLI

```bash
uv tool install git+https://github.com/yash-srivastava19/cadence
```

Create a project in an empty directory:

```bash
mkdir my-cadence-project
cd my-cadence-project
cadence init
```

`init` writes four files:

| File | Purpose |
| --- | --- |
| `solve.py` | The program. Only the marked region changes. |
| `score.py` | Runs the candidate and prints the declared metrics. |
| `.cadence` | The experiment manifest. |
| `IMPROVE.md` | Guidance sent with every model prompt. |

## Choose a provider

The generated manifest uses Gemini. Put its key in the environment, not in the manifest:

```bash
export GEMINI_API_KEY=your-key-here
```

For a local model, change the manifest to an Ollama provider:

```yaml
model:
  ollama:
    model: your-local-model
```

See [Environment](../reference/environment.md) for supported provider keys.

## Check before spending

```bash
cadence check
```

This runs the baseline but does not call the model. Read the output for:

- The editable region.
- The scoring command and baseline verdict.
- The metric direction.
- Seeds and sandbox limits.
- Estimated scoring work and model budget.
- Whether the run will be recorded.

If `check` does not say `ready`, fix the reported problem before running the search.

## Run the search

```bash
cadence run
```

The progress stream reports each trial. Without `DATABASE_URL`, the result is written to the terminal and the JSONL log under `cadence-runs/`. With a database configured, the run gets a durable ID and can be inspected or resumed later.

## Next steps

- Follow the [first experiment tutorial](../tutorials/first-experiment.md).
- Learn how to [bring your own program](../guides/bring-your-own-program.md).
- Read [what `check` is protecting](../concepts/harness.md).
