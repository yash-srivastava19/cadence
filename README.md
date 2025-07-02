# Cadence - Program Evolution via Language Models

Cadence implements an evolutionary system that uses large language models (LLMs) to iteratively generate, mutate, and improve programs for solving computational problems. The current implementation focuses on optimizing solutions to the Traveling Salesman Problem (TSP).

## Overview

The system evolves programs over generations using the following loop:

1. Sample a parent program and its previously generated children.
2. Construct a prompt that includes the parent, children, and instructions.
3. Use an LLM to generate modified versions of marked code blocks.
4. Apply the generated diffs to produce a child program.
5. Evaluate the child program's performance on a fixed test suite.
6. Log and store the program and its performance in a database.
7. Periodically promote the best-performing program to guide future generations.
8. Optionally mutate the instructions used in prompts to encourage better code.

## Features

* TSP solution evolution using only standard Python (no external math libraries)
* Multi-seed deterministic evaluation for stable cost metrics
* SQLite-backed storage of program generations and performance
* Parallel evaluation for faster feedback
* Meta-prompting: periodically updates instructions to steer LLM behavior
* Modular task abstraction to support other optimization problems in the future

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/yash-srivastava19/cadence
cd cadence
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies with uv (recommended)


```bash
uv pip install
```

### 4. Add API Keys

Create a `.env` file with your model API key. I used Gemini, so in the .env file, add this:

```
GEMINI_API_KEY=your-key
```

### 5. Run the Evolution Script

```bash
python main.py
```

This will evolve TSP solvers over multiple generations and save the progress in `experiment_log.json`.

### 6. Visualize Results

```bash
python analyze_results.py
```

This will generate a line plot showing how the TSP cost evolved over generations.

## Directory Structure

```
src/
├── database.py          # SQLite DB for storing programs
├── evolve.py            # Applies diffs to code blocks
├── evaluator.py         # Evaluates cost on multiple TSP inputs
├── llm.py               # Handles LLM interaction (OpenAI or Gemini)
├── prompt_sampler.py    # Builds structured prompt for LLM
├── task.py              # Task abstraction interface
└── tasks/
    └── tsp_task.py      # TSP task logic
```

## Notes

* All code blocks must be marked with `### START_BLOCK` and `### END_BLOCK`.
* Prompts are built to explicitly instruct the LLM to only change marked blocks.
* Evaluation is deterministic using seeded inputs.
* The project uses `uv` for reproducible dependency management and performance.

## Extending

To make cadence work for problems beyond TSP, you can define your own custom tasks by implementing the `Task` interface. This makes the system problem-agnostic while keeping the core workflow intact.

### Step 1: Create a New Task File

Create a new Python file in `src/tasks/`, for example:

```bash
touch src/tasks/knapsack_task.py
```

### Step 2: Implement the Task Interface

Each task must subclass `Task` and implement the following:

```python
from src.task import Task

class YourTask(Task):
    @property
    def function_name(self):
        # Name of the function LLM is expected to generate
        return "solve"

    def generate_inputs(self, seed: int):
        # Generate deterministic input using the seed
        return ...

    def evaluate(self, output, input_data) -> float:
        # Return a numerical metric (lower is better)
        return ...
```

* `function_name`: This must match the name of the function the LLM is expected to define.
* `generate_inputs(seed)`: Generate problem input. This can be a list, tuple, or dict.
* `evaluate(output, input_data)`: Accepts output from the evolved program and returns a numeric cost.

### Step 3: Use the Task in `main.py`

Import your task class and instantiate it:

```python
from tasks.knapsack_task import KnapsackTask
task = KnapsackTask()
```

Then pass it into the `execute()` function:

```python
metric = execute(child_program_code, task)
```

### Tips

* Use only standard Python libraries (`math`, `itertools`, `re`, etc.).
* Keep test inputs deterministic via seeds.
* Define a cost metric that is meaningful, consistent, and scalar.
* Try to avoid relying on `random` inside the generated programs themselves.



## License

MIT License

---


### worklog
18/05/2025:
worked on researching what kind of problems exists that fit the description, and laid down the structure(and boilerplate) for the project, named it cadence. Some of the interesting problems I found out were:

1. root finding.
2. prime factorization.
3. inverse of a matrix.
4. fft optimization.
5. minimum makesplan scheduling with precedence.
6. rectangle packing.
7. collatz conjecture iteration count.
8. digital root calculation.

Will try to find more that fits this description, and work on one file at a time. We have the foundations laid down, just need to fill in an run experiments.

19/05/2025:
Worked on basic versions of all the db, eval, llm, sampler(not evolve because it will be based on problem). Used SQLite for DB, and apply_diff uses `re`. The work is going on nice, and now would like to continue and run them in a pipeline.

15/06/2025:
Working for TSP problem, however not evolving too much. Improved the DB, evaluator, prompts and other functions, and using gemini for program evals. working on improving the strategy to make cost go down.

Made the task general so that they can be used for a variety of problems. Added async calls and logging. CLI added too and updated the README.

22/06/2025
RL not actually improving
- RL + LLM reward modelling.
- `train_rl` barebones is now ready.
- examples are now added, will add more.
- Fallback when no parent code is there.
- analyze result now works for RL and LLM case.


26/06/2025
- Need to focus on improving the prompt and output strategy. Novelty, heuristics and all were considered and added.

27/06/2025
- Added resumed checkpointing. Gemini exhausted. Did some code refactors.

30/06/2025
- Code refactors + Gemini 2.5 Pro

02/07.2025
- Code refactors + Experiments +
