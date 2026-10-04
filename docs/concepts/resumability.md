# Resumability

Cadence separates three recovery problems. They are related, but they are not the same feature.

| Level | What survives | Why it matters |
| --- | --- | --- |
| Model call | A content-addressed request and response | A retry does not pay for the same question twice. |
| Trial | The settled candidate and its verdict | A stopped worker can continue without replaying completed work. |
| Experiment | Parents, metrics, lineage, and configuration | The search resumes with the history that shaped selection. |

The database is the checkpoint. The process and the machine running it are disposable.

## What a resume is not

Resuming is not starting a new run from a good program. A new run has a new identity and a new history. A resumed run continues the existing experiment.

## Operational limits

The current system is designed for one operator on a trusted local setup. The dashboard is read-only and bound to localhost. There is not yet a lease or heartbeat that prevents two operators from resuming the same run at once.
