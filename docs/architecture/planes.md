# System planes

The package is organized around responsibilities. A plane may depend on the lower-level facts it needs, but it should not reach across another plane to recreate its behavior.

| Plane | Owns | Does not know |
| --- | --- | --- |
| `commands` | CLI input and exit behavior | How candidates are executed. |
| `web` | Read-only browser delivery | How the search makes decisions. |
| `delivery` | Human and JSON presentation | Provider or sandbox implementation. |
| `control` | Search, prompts, patches, objectives, and recording | How a candidate process is isolated. |
| `execution` | Sandbox, limits, metric collection, and verdicts | Why a parent was selected. |
| `parsing` | Reading declared metrics | Search policy. |
| `observe` | Publishing run facts | Presentation details. |
| `core` | DTOs, identities, ports, and value types | Concrete adapters. |

The web plane is a sibling entry point to the command plane. Both ask the same control and delivery layers for facts, so the browser cannot silently invent a different interpretation of a trial.

## Why the dashboard is read-only

Showing a run is a delivery problem. Starting or modifying one is a control problem requiring ownership, leases, and authentication. The current dashboard stays read-only and localhost-bound until those questions have real answers.
