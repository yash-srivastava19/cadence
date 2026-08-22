# Examples

Every example on this page runs against the current code. They go from
scoring a single program to driving a full loop by hand.

There is no `EvolutionSystem` class. The loop is assembled from four
functions, which is what the last example shows.

## Score a program

The smallest useful thing you can do.

```python
from src.evaluator import execute
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)
print(execute(task.baseline_program, task))
```

## Compare two programs on the same seeds

Use this to check that a change actually helped, and that your task can tell
the difference.

```python
from src.evaluator import execute
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=12)
seeds = [1, 2, 3, 4, 5]

nearest_neighbour = """### START_BLOCK
def tsp(cities):
    unvisited = set(range(1, len(cities)))
    tour = [0]
    while unvisited:
        last = cities[tour[-1]]
        nxt = min(
            unvisited,
            key=lambda i: (cities[i][0] - last[0]) ** 2 + (cities[i][1] - last[1]) ** 2,
        )
        tour.append(nxt)
        unvisited.remove(nxt)
    return tour
### END_BLOCK"""

for name, code in [("baseline", task.baseline_program), ("nearest", nearest_neighbour)]:
    result = execute(code, task, seeds=seeds)
    print(f"{name:10s} cost {result['cost']:8.2f}  feasibility {result['feasibility']}")
```

Nearest-neighbour should beat the identity-permutation baseline by a wide
margin. If it does not, something is wrong with the task, not the heuristic.

## Find out why a program is failing

`execute()` reports `feasibility` but not the reason. `evaluate_on_task()`
keeps the error text.

```python
from src.evaluator import evaluate_on_task
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)

broken = """### START_BLOCK
def tsp(cities):
    return [0, 0, 0]
### END_BLOCK"""

namespace = {}
exec(broken, namespace)
solver = namespace["tsp"]

for seed in (1, 2):
    print(seed, evaluate_on_task(solver, task, seed))
```

```text
1 {'cost': 100000000.0, 'feasible': False, 'error': 'Tour is not feasible'}
2 {'cost': 100000000.0, 'feasible': False, 'error': 'Tour is not feasible'}
```

## Replace a block by hand

`apply_diff()` is what turns a model response into a child program. Despite
the name, it is not a diff: **each string replaces one whole marked block, in
order.** There is no search text and no context matching.

```python
from src.evolve import apply_diff
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)

new_block = """def tsp(cities):
    return sorted(range(len(cities)), key=lambda i: cities[i][0])"""

print(apply_diff(task.baseline_program, [new_block]))
```

```text
### START_BLOCK
def tsp(cities):
    return sorted(range(len(cities)), key=lambda i: cities[i][0])
### END_BLOCK
```

The markers are re-added for you, and the replacement is stripped of outer
whitespace. Pass one string per block, in the order the blocks appear:

```python
from src.evolve import apply_diff

parent = "### START_BLOCK\nA\n### END_BLOCK\nkeep me\n### START_BLOCK\nB\n### END_BLOCK"
print(apply_diff(parent, ["A2", "B2"]))
```

Give it fewer strings than there are blocks and the extra blocks are left
exactly as they were — silently. That is why the prompt tells the model
"You MUST output the same number of blocks as in the parent program": a short
response does not fail, it just changes less than you think.

## Read a finished run

```python
from src.database import Database
from src.models import DatabaseConfig

db = Database(DatabaseConfig(database_path="cadence_db.sqlite"))

best = db.get_best_program()
if best is None:
    print("no programs yet -- run an experiment first")
else:
    print(f"generation {best.generation}  cost {best.metric:.2f}")
    print(best.code)
```

`get_best_program(generation_limit=N)` restricts the search to generations up
to `N`, which is how you reconstruct what the best-so-far was at any point.

## One generation, by hand

The whole loop, with nothing hidden. This one calls the model, so it needs
`GEMINI_API_KEY` and costs a request.

```python
from src.database import add, sample
from src.evaluator import execute
from src.evolve import apply_diff
from src.llm import generate
from src.prompt_sampler import build
from src.tasks.tsp_task import TSPTask

task = TSPTask(n_cities=10)

# Generation 0: seed the database with the baseline.
baseline_cost = execute(task.baseline_program, task)["cost"]
add(parent_id=None, program_code=task.baseline_program, metric=baseline_cost)

# Generation 1: sample, prompt, mutate, score, store.
parent, inspirations = sample(generation_number=0)
prompt = build(parent, inspirations, lesson=None)
diffs = generate(prompt)

child_code = apply_diff(parent[3], diffs)
child = execute(child_code, task)
add(parent_id=parent[0], program_code=child_code, metric=child["cost"])

print(f"parent {parent[4]:.2f} -> child {child['cost']:.2f}")
```

Wrap that in a `for` loop over generations and you have `main.py`, minus the
lesson extraction, the elitism schedule, and the error handling.

## See also

- [Tasks](tasks.md) — a complete custom task
- [Evolution pipeline](evolution.md) — what each of those calls does
- [Experiments](experiments.md) — the scripted versions of the last example
