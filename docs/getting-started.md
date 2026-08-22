# Getting started

By the end of this page you will have run an evolution, read its output, and
know which knob to turn next. It takes about ten minutes and roughly 30 Gemini
calls.

## Before you start

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

## 1. Install

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
uv sync
source .venv/bin/activate
```

On Windows the last line is `.venv\Scripts\activate`.

## 2. Set your key

Cadence reads one environment variable, `GEMINI_API_KEY`.

```bash
export GEMINI_API_KEY="your-key-here"
```

To keep it across shells, put it in `.env` at the project root instead.
`.env` is in `.gitignore`; keep it that way.

```bash
echo 'GEMINI_API_KEY=your-key-here' >> .env
```

Check it took:

```bash
python -c "from src.llm import LLMProvider; LLMProvider(); print('key ok')"
```

A missing or misspelled key raises `LLMError: GEMINI_API_KEY environment
variable not set`. That is the single most common setup failure.

## 3. Run an evolution

```bash
python run_h1_experiment.py
```

The run has three phases, and says so:

```text
[1] Running baseline heuristics...
Baseline added with cost: 812.44
[2] Running LLM evolution...
INFO  Using lesson for generation 5: prefer swapping adjacent pairs ...
INFO  Elitism: breeding from best program 11 (cost 742.1305)
[3] Plotting results...
Saved combined plot to h1_results.png
```

`cost` is total tour length across the evaluation seeds. Lower is better. It
moves down unevenly — most generations produce nothing better, which is normal
for this kind of search.

When it finishes you have three files in the project root:

| File | Contents |
| --- | --- |
| `h1_results.png` | Best cost per generation, against two hand-written baselines |
| `experiment_log.json` | Every generation: cost, parent, and the code that was produced |
| `lesson_history.json` | What the model concluded, one entry per lesson interval |

Programs also go to `cadence_db.sqlite`, which is what the web interface reads.

## 4. Read the result

The plot answers one question: did evolution beat the baselines? The two
reference lines are nearest-neighbour and a reversal heuristic, computed in
`run_baselines()`. If the evolved curve does not get under them, the run
failed — see below.

To pull the best program out:

```python
import json

with open("experiment_log.json") as f:
    log = json.load(f)

best = min(log, key=lambda entry: entry["cost"])
print(f"generation {best['generation']}  cost {best['cost']:.2f}")
print(best["child_code"])
```

Each entry carries `generation`, `cost`, `feasibility`, `parent_code`,
`child_code`, `parent_cost`, `child_cost`, `hash`, and `lesson`.

## 5. Turn one knob

Every setting is a Hydra key. Override it on the command line — no file
editing:

```bash
python run_h1_experiment.py GENERATIONS=60 LESSON_INTERVAL=3
```

Longer runs cost proportionally more. [Configuration](configuration.md) lists
every key that each script actually reads.

## When something goes wrong

**`LLMError: GEMINI_API_KEY environment variable not set`**
`src/llm.py` calls `load_dotenv()` on import, so a `.env` at the project root
is picked up automatically — but only when you run from the project root.
`echo $GEMINI_API_KEY` to check the shell, and confirm your working directory.

**Every generation logs `Generation N failed`**
The model is returning text that does not parse as a `SEARCH`/`REPLACE` diff,
so nothing applies. Look at `experiment_log.json` for the raw response.
Usually the baseline program is missing its `### START_BLOCK` /
`### END_BLOCK` markers, and there is nothing for the model to edit.

**Cost never improves**
Check the plot's baselines. If your task's scoring function cannot separate a
good program from a bad one, the search is a random walk that still reports a
winner. Score your baseline and a deliberately worse program by hand; if they
land within noise of each other, fix the scoring function first.

**The run hangs**
A generated program contains an infinite loop. There is no timeout — see the
limits in the [overview](index.md#what-cadence-does-not-do-yet). Interrupt it.
Generations completed so far are already in `experiment_log.json`, and
`run_h1_experiment.py` picks up from that file if it exists. `main.py` does
the same, unless `FORCE_RERUN=true`, which deletes the log and starts over.

## Next

- [Tasks](tasks.md) — point Cadence at your own problem
- [Evolution pipeline](evolution.md) — how parents are chosen and lessons are used
- [Web interface](web-interface.md) — watch a run in the browser
