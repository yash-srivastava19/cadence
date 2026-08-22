# Visualising results

Cadence writes two things you can plot: `experiment_log.json`, one entry per
generation, and `cadence_db.sqlite`, one row per program. The experiment
scripts already produce a plot; this page is for when you want your own.

Both live in the run's Hydra output directory unless you passed
`hydra.run.dir=.` — see [Configuration](configuration.md#where-output-goes-and-the-gotcha).

## From the database

`get_all_programs()` returns `ProgramEntry` objects with `generation`,
`metric`, `parent_id`, and `code`.

```python
import matplotlib.pyplot as plt
from src.database import Database
from src.models import DatabaseConfig

db = Database(DatabaseConfig(database_path="cadence_db.sqlite"))
programs = db.get_all_programs()

generations = [p.generation for p in programs]
costs = [p.metric for p in programs]

fig, ax = plt.subplots(figsize=(8, 4))
ax.scatter(generations, costs, s=12, alpha=0.6)
ax.set_xlabel("generation")
ax.set_ylabel("cost")
ax.grid(True, alpha=0.3)
fig.savefig("evolution.png", dpi=150)
```

Every program appears, including failures. Those sit at `1e8` and will flatten
your axis — filter them out:

```python
real = [(p.generation, p.metric) for p in programs if p.metric < 1e8]
```

## Best-so-far, which is the curve that matters

A scatter of every candidate shows how noisy the search is. The running
minimum shows whether it is working.

```python
import matplotlib.pyplot as plt
from src.database import Database
from src.models import DatabaseConfig

db = Database(DatabaseConfig(database_path="cadence_db.sqlite"))
feasible = sorted(
    ((p.generation, p.metric) for p in db.get_all_programs() if p.metric < 1e8),
)

best_so_far, running = [], float("inf")
for generation, cost in feasible:
    running = min(running, cost)
    best_so_far.append((generation, running))

fig, ax = plt.subplots(figsize=(8, 4))
ax.step(*zip(*best_so_far), where="post")
ax.set_xlabel("generation")
ax.set_ylabel("best cost so far")
fig.savefig("best_so_far.png", dpi=150)
```

A flat line for many generations means the search has stalled, and more budget
will not help.

## From the experiment log

```python
import json

with open("experiment_log.json") as f:
    log = json.load(f)

improved = sum(
    1
    for entry in log
    if entry["parent_cost"] is not None and entry["child_cost"] < entry["parent_cost"]
)
print(f"{improved} of {len(log)} generations beat their parent")
```

That ratio is the most useful single number about a run. If it is near zero,
the model is not producing useful edits and the prompt is the thing to change.
