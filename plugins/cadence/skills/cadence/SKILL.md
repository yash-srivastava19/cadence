---
name: cadence
description: Help users design, validate, run, inspect, and resume Cadence experiments without confusing measurement failures with scores.
---

# Cadence project workflow

Use this skill when a user wants to use Cadence on a program, heuristic, simulator, scheduler, proof tactic, or other executable problem.

## Source of truth

Read the current Cadence documentation before inventing commands or configuration:

- Overview: https://cadence.readthedocs.io/en/latest/
- Harness design: https://cadence.readthedocs.io/en/latest/concepts/harness/
- Bring your own program: https://cadence.readthedocs.io/en/latest/guides/bring-your-own-program/
- Manifest: https://cadence.readthedocs.io/en/latest/reference/manifest/
- CLI: https://cadence.readthedocs.io/en/latest/reference/cli/
- Verdicts: https://cadence.readthedocs.io/en/latest/concepts/verdicts/

## Workflow

1. Ask what program or function should improve.
2. Ask what the scoring command can measure and how it decides that one result is better.
3. Identify the smallest safe editable region. Keep the interface and scorer outside it.
4. Ask for the baseline behavior and how invalid output should be classified.
5. Ask whether the problem needs training, validation, and held-out data.
6. Create or explain `program`, scorer, `.cadence`, and `IMPROVE.md`.
7. Run `cadence check` before `cadence run`.
8. Explain every warning, limit, seed, metric direction, and expected budget.
9. Ask how noisy the score is. If repeated runs of one program differ, recommend `pick: confirm` with seeds the search does not use, so the reported winner is not just the luckiest measurement. If scoring is slow, mention `judge: cascade`. Cite the manifest reference.
10. Ask for confirmation before starting a run that can spend model calls.
11. After the run, distinguish scored candidates from crashes, timeouts, verifier errors, and provider failures.
12. Recommend held-out evaluation before calling a candidate a general improvement.
13. Explain `cadence run --resume RUN_ID` and `cadence apply RUN_ID` before using either.

## Non-negotiable rules

- A failure is never a zero.
- A scorer that the candidate can rewrite is not a stable experiment.
- `cadence check` is required before an expensive run.
- A validation improvement is not evidence of generalization by itself.
- The best of many noisy measurements is partly luck. Report a winner's confirmed score when there is one, not only its score during the search.
- `cadence apply` overwrites the configured program; tell the user to commit first.
- Do not start, resume, apply, migrate, or delete anything without explicit confirmation.

## Output style

Explain the reason behind each recommendation. Cite the documentation page that supports it. If the docs do not establish a behavior, say that clearly instead of guessing.
