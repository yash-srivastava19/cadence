# The mental model

Cadence is an experiment runner for programs whose quality can be measured. It uses a model as a proposal mechanism, not as the authority that decides whether a proposal is good.

That distinction is the whole product in miniature:

> **The model suggests. Your harness measures. Cadence keeps the evidence.**

## One trial

```text
project files
    ↓ copy into a temporary working directory
candidate patch
    ↓ apply only inside the marked region
scoring command
    ↓ run with the declared seed and sandbox limits
verdict
    ↓ record the candidate, evidence, and reason
selection
    ↓ choose what becomes a parent for the next trial
```

The candidate does not see or rewrite the scoring command. The scoring command does not decide which candidate gets proposed next. Those boundaries make the experiment easier to reason about.

## Why the loop has these steps

| Step | Question it answers |
| --- | --- |
| Mark | What part of the program is open to exploration? |
| Propose | What change is worth trying next? |
| Apply | Can the proposal become a candidate without changing the shell? |
| Measure | What did this exact candidate do on these exact inputs? |
| Classify | Was the result a score, or did measurement fail? |
| Select | Which evidence should influence the next proposal? |

The order matters. Selection before measurement would be a guess. Measurement without classification would confuse a broken scorer with a weak algorithm.

<details>
<summary>What a single candidate looks like on disk</summary>

```text
temporary trial directory/
├── solve.py       # candidate written over the marked region
├── score.py       # copied from the project; not editable by the candidate
├── IMPROVE.md     # prompt guidance
└── input data     # whatever the project deliberately includes
```

Cadence runs the scoring command in this temporary directory with the declared seed and limits. The exact files and sandbox behavior are part of the experiment's contract.

</details>

## What you own

- The program and editable region.
- The scoring command.
- The metric definitions and direction.
- The baseline.
- The seeds and data split.
- The guidance in `IMPROVE.md`.

## What Cadence owns

- Asking a provider for a proposal.
- Applying the proposal.
- Running the candidate in the sandbox.
- Classifying the result as a verdict.
- Selecting parents and tracking lineage.
- Recording enough history to inspect and resume the run.

## The seam is deliberate

Cadence does not need to know whether your candidate is Python, Lean, a scheduling policy, or a cache replacement rule. It needs a program region, a command that can measure it, and a declared way to rank the result.

That is why the documentation starts with experiment design rather than with Python classes.
