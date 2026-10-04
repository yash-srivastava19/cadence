# Use Cadence with AI agents

Cadence publishes a small, installable skill for agents that help users create and inspect Cadence projects. It is not a conversational documentation product and it does not start model runs by itself.

## Install the Claude Code plugin

Claude Code can install the Cadence skill through the repository's plugin
marketplace. This is the preferred path because Claude Code can track the
plugin and update it as the repository changes.

From Claude Code:

```text
/plugin marketplace add yash-srivastava19/cadence
/plugin install cadence@cadence
/reload-plugins
```

The plugin currently contains the Cadence workflow skill. It does not start
runs, modify files, or install an MCP server without a separate future decision.

## Install the skill directly

Use the published skill URL in an agent client that supports remote skills:

```text
https://cadence.readthedocs.io/en/latest/.well-known/skills/cadence/SKILL.md
```

For a Claude Code project, install it locally so it is available whenever you
work in that repository:

```bash
mkdir -p .claude/skills/cadence
curl -fsSL \
  https://cadence.readthedocs.io/en/latest/.well-known/skills/cadence/SKILL.md \
  -o .claude/skills/cadence/SKILL.md
```

To make it available across projects, use `~/.claude/skills/cadence/` instead
of `.claude/skills/cadence/`.

For clients that install skills from a Git repository, use the `SKILL.md` at the same path in the Cadence repository. The repository version is the source used to publish the docs version.

## What the skill does

The skill helps an agent:

- Translate a problem into a marked program, scorer, manifest, and guidance file.
- Explain why the scorer must remain outside the editable region.
- Choose metric directions, seeds, validation data, and sandbox limits.
- Run `cadence check` before asking for confirmation to spend model budget.
- Interpret verdicts and local run logs.
- Explain how to resume or apply a winner without hiding destructive behavior.

## What it does not do

The skill does not:

- Start a model run without explicit user confirmation.
- Treat a failed candidate as a score.
- Claim that a validation improvement generalizes to held-out data.
- Invent provider names, manifest fields, or supported guarantees.
- Replace the documentation reference pages.

## Machine-readable entry points

- [`/llms.txt`](https://cadence.readthedocs.io/en/latest/llms.txt): Curated docs index and instructions for agents.
- [`/llms-full.txt`](https://cadence.readthedocs.io/en/latest/llms-full.txt): The generated full Markdown corpus.
- [`/.well-known/skills/index.json`](https://cadence.readthedocs.io/en/latest/.well-known/skills/index.json): Skills catalog.
- [Manifest reference](reference/manifest.md): Exact configuration fields.
- [CLI reference](reference/cli.md): Exact commands and output behavior.

The docs site is the source of truth. When Cadence behavior changes, the skill and these entry points must change in the same pull request.
