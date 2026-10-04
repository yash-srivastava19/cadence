# Design decisions

Cadence is deliberately opinionated. These decisions are the reason the system has the shape it does, and they are more useful to understand than a list of modules.

## The model proposes; the scorer decides

Cadence uses a language model to propose changes because proposal is the part of the problem where a model can be useful. It does not ask the model whether the change is good. The scoring command measures the candidate, and the declared objective ranks the result.

This separation keeps the authority to judge outside the thing being judged.

## The editable region is smaller than the project

The model receives a bounded region rather than an unrestricted repository. This gives the experiment a stable shell: imports, interfaces, test data, and the scoring command can remain fixed while the candidate explores an algorithm.

It also makes the unit of change visible. A reader can inspect exactly what was offered to the model and what it was allowed to rewrite.

## A failure is never a zero

A zero is a measurement. A crash is an event that prevented measurement. Treating both as a number makes the objective lie and can reward broken candidates. Cadence therefore carries scores and failures as different verdict types.

## The database is a checkpoint, not a report cache

Runs can last longer than a process, a machine, or a provider quota. The durable record therefore contains the facts needed to rebuild the search: identities, candidates, prompts or hashes, measurements, verdicts, and lineage.

The worker can be disposable because the experiment history is not held only in memory.

## Preflight is a product feature

`cadence check` exists because an expensive search can be perfectly healthy while measuring the wrong thing. It runs no model calls, but it validates enough of the harness to say what will happen, what it will cost, and what would stop the run.

That is why `check` is not merely a convenience command. It is the point where a hypothesis meets its measuring instrument.

## The browser is read-only for now

The dashboard reads the same record as the CLI. It does not start runs or apply candidates. Acting on a run requires answers about ownership, leases, authentication, and concurrent resume. Keeping the web plane read-only avoids pretending those questions are solved.

## The language belongs to the problem

Cadence can evolve a Python heuristic, a Lean tactic, or a scheduling policy because its seam is a program plus a scoring command. The loop does not need to understand the candidate language. The sandbox and scorer do.

!!! note "A boundary is a promise"
    The less Cadence assumes about the problem, the more carefully the project must describe its own interface, inputs, outputs, and failure behavior.
