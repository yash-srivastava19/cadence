# Resume and inspect a run

Use durable recording when an experiment can outlive one terminal session, provider quota, or machine.

## Configure recording

Set `DATABASE_URL` before running:

```bash
export DATABASE_URL=postgresql://cadence:cadence@localhost:5433/cadence
cadence db upgrade
```

Without `DATABASE_URL`, Cadence still runs and writes local JSONL logs, but database-backed run queries and resume are unavailable.

## List and inspect runs

```bash
cadence runs list
cadence runs show RUN_ID
cadence trials list --run RUN_ID
cadence trials show TRIAL_ID
```

Use `--json` when another tool or agent will consume the result.

## Resume after a stop

```bash
cadence run --resume RUN_ID
```

Cadence restores the recorded experiment history and continues from settled work. Model calls that have already been paid for can be replayed from durable records rather than requested again.

## Apply a winner

```bash
cadence apply RUN_ID
```

This overwrites the configured program with the best candidate. Commit or copy the project first; `apply` does not create a backup.

## Read the local log

Each run writes JSONL under `cadence-runs/`:

```text
cadence-runs/
└── development/
    └── <run-id>.jsonl
```

The log records the run as append-only facts: model calls, patches, measurements, verdicts, warnings, and failures. Candidate source and prompts are represented by hashes except where the local failure detail is intentionally retained.
