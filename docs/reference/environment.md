# Environment reference

Cadence reads credentials and operational settings from the environment, never from `.cadence`.

## Provider credentials

| Variable | Provider |
| --- | --- |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini |
| `OPENAI_API_KEY` | OpenAI-compatible provider |
| `ANTHROPIC_API_KEY` | Anthropic |
| `OLLAMA_HOST` | Optional Ollama address override |

## Recording and logs

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | Database used to record and query runs. If unset, the run is not recorded in the database. |
| `CADENCE_ENV` | Names the local JSONL log environment directory. Defaults to `development`. |
| `CADENCE_SEED` | Seed supplied to the scoring command for the current trial. |

Cadence also reads a `.env` file in the current project directory. Existing shell variables win over values in that file.

## Security boundary

Provider keys are not passed to the scoring command. The sandbox gets a clean environment plus the seed needed by the project. The current sandbox does not restrict network access or files outside the working copy; treat it as a bounded execution environment, not a complete security boundary.
