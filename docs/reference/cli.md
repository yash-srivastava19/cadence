# CLI reference

Cadence uses one command-line interface for project setup, preflight, execution, inspection, and database administration.

## Project and execution

| Command | Purpose |
| --- | --- |
| `cadence init [DIR]` | Create a project that `check` can inspect. |
| `cadence check [DIR]` | Validate the project and report what a run would do without calling a model. |
| `cadence run [DIR]` | Run the search. |
| `cadence run --resume RUN_ID` | Continue a recorded run. |
| `cadence run --config FILE` | Use a manifest other than `DIR/.cadence`. |
| `cadence apply RUN_ID [DIR]` | Write the best program from a run over the configured program. |
| `cadence schema` | Print the manifest JSON Schema. |

## Recorded runs and trials

These commands require `DATABASE_URL`:

```bash
cadence runs list
cadence runs show RUN_ID
cadence trials list --run RUN_ID
cadence trials show TRIAL_ID
```

The commands accept `--json`. JSON is also the default when output is not a terminal.

## Database

```bash
cadence db status
cadence db upgrade
cadence db upgrade --url postgresql://owner:...
cadence db rollback --to -1
```

`rollback` asks for confirmation because it can remove tables. Keep the migration URL separate from the application URL when the database uses distinct owner and application roles.

## Dashboard

```bash
cadence dashboard
cadence dashboard --port 9000
```

The dashboard is read-only and binds to localhost. It reads the same recorded data exposed by the run and trial commands. It has no authentication; anyone who can reach the bound address can read the manifests and candidate programs.

## Output and exit behavior

Human-readable commands print one sentence per problem where possible and use a non-zero exit code when the requested operation cannot continue. Use `--json` for stable machine-readable output rather than parsing terminal prose.
