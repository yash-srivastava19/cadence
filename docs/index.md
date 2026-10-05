<div class="eyebrow">Cadence · alpha · cadence/v1alpha2</div>

# Evolve code you can measure.

Mark the part of a program a model may rewrite, name the command that scores it, and Cadence searches for a better version inside a sandbox.

<div class="grid cards" markdown>

-   **01 · Learn by doing**

    Run a complete experiment with a small program, a scoring command, and a bounded budget.

    [First experiment →](tutorials/first-experiment.md)

-   **02 · Use your own problem**

    Bring a heuristic, scheduler, simulator, or proof tactic. Cadence does not need to know its language or domain.

    [Bring your own program →](guides/bring-your-own-program.md)

-   **03 · Understand the system**

    Learn why the editable region, scorer, verdicts, and durable history are separate.

    [Read the concepts →](concepts/index.md)

-   **04 · Look up exact behavior**

    Find CLI commands, manifest fields, environment variables, and recorded output.

    [Open the reference →](reference/cli.md)

</div>

## The experiment in one line

You bring three things. Cadence supplies the search loop and the record of what happened.

<div class="flow" markdown>
<div class="flow-step"><small>01</small><strong>Marked<br>program</strong><span>the region you expose</span></div>
<i>→</i>
<div class="flow-step"><small>02</small><strong>Model<br>patch</strong><span>one change to try</span></div>
<i>→</i>
<div class="flow-step"><small>03</small><strong>Scoring<br>command</strong><span>your measurement</span></div>
<i>→</i>
<div class="flow-step"><small>04</small><strong>Verdict</strong><span>score or reason</span></div>
<i>→</i>
<div class="flow-step"><small>05</small><strong>Next<br>parent</strong><span>best evidence so far</span></div>
</div>

<figure markdown>
  ![A Cadence trial moving from proposal to measurement and recording](assets/illustrations/trial-loop.gif){ loading=lazy }
  <figcaption>One trial, stepped through. The model proposes a change; the scorer stays outside the editable region.</figcaption>
</figure>

```yaml title=".cadence"
api_version: cadence/v1alpha2
program: solve.py
run: python score.py
metrics:
  score: maximize
budget:
  trials: 20
model:
  gemini: {}
```

```bash
cadence check  # inspect the run; spends nothing
cadence run    # propose, measure, keep what improved
```

## What Cadence protects

| Boundary | Why it matters |
| --- | --- |
| The marked region | The model can change only what you expose. |
| The scoring command | A candidate cannot rewrite the code that judges it. |
| The manifest | Metrics, budget, model, seeds, and limits are explicit and recorded. |
| The verdict | A crash, timeout, verifier error, and score are different outcomes. |
| The run history | A stopped machine does not erase measured evidence. |

!!! warning "Alpha software"
    The manifest format is versioned and breaking changes are expected before a stable release. The sandbox limits time, memory, output, and environment exposure, but does not currently restrict network access or files outside the working copy.

## Choose a path

| You want to... | Start here |
| --- | --- |
| Run Cadence once | [Get started](get-started/index.md) |
| Learn the whole workflow | [First experiment](tutorials/first-experiment.md) |
| Use your own algorithm | [Bring your own program](guides/bring-your-own-program.md) |
| Make the result trustworthy | [Design the harness](concepts/harness.md) |
| Recover after a stop | [Resume and inspect a run](guides/resume-and-inspect.md) |
| Find a flag or field | [CLI reference](reference/cli.md) or [Manifest reference](reference/manifest.md) |
| Understand the implementation | [Architecture](architecture/index.md) |
| See real evidence | [Experiments and evidence](research/index.md) |

## For people building with agents

Cadence documentation is intended to be usable by coding agents as well as people. An agent should help you design the scoring harness, run `cadence check`, explain warnings, and cite the page that supports its advice. It should not invent a score, hide a failure, or start an expensive run without making the budget visible.

The agent workflow is documented in [Design the harness](concepts/harness.md) and [Bring your own program](guides/bring-your-own-program.md).
