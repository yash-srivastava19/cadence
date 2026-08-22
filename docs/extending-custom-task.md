# Extending Cadence

Cadence works on any problem you can score. To add one, implement the `Task`
interface: `function_name`, `generate_inputs`, `evaluate`, and
`baseline_program`.

**[Tasks](tasks.md) is the full guide**, with a complete worked knapsack
example, the rules about cost direction and determinism, and how to check that
your scoring function can tell a good program from a bad one before you spend
anything on a run.

This page used to carry a second, shorter copy of that walkthrough. Two
versions of the one thing every user must write is one version too many.
