"""Starting a project, correctly, without having read anything first.

Six of the nine ways a first project goes wrong are shape mistakes: no
markers, no metric printed, a metric under a different name than the manifest
asks for, a program the manifest cannot find, scoring inside the region. A
generated project cannot make any of them, which is cheaper than diagnosing
them one at a time.

Two files rather than one on purpose. `solve.py` is what the model rewrites;
`score.py` decides what that was worth. Put both in one file and the model
ends up owning the line it is judged by -- see `cadence check`'s scoring
finding, which exists because that mistake is invisible once it is made.
"""

from pathlib import Path

import typer

from cadence.commands.report import die, found, note
from cadence.control.manifest import FILENAME

MANIFEST = """\
api_version: cadence/v1alpha2
program: solve.py
experiment: {name}

# solve.py is edited; score.py decides what it is worth. Keeping them apart
# is what stops a candidate from setting its own score.
run: python score.py

metrics:
  score: maximize

budget:
  trials: 20

model:
  gemini: {{}}
"""

SOLVE = '''\
"""The part cadence rewrites.

Only what is between the markers changes. Everything else stays, or two
trials would not be comparable.
"""


# CADENCE:BEGIN
def solve(problem: list[int]) -> int:
    """Replace this with something better.

    Right now it adds the numbers up. Whatever you write has to keep the
    name, take the same argument, and return a number.
    """
    return sum(problem)


# CADENCE:END
'''

SCORE = '''\
"""What a solution is worth. Not editable, which is the point.

Prints one line, `score: <number>`, which is the name .cadence asks for. If
this lived in solve.py the model could print whatever it liked.
"""

from solve import solve

PROBLEM = [3, 1, 4, 1, 5, 9, 2, 6]


def main() -> None:
    answer = solve(PROBLEM)
    # Replace with a real measure of your problem. A wrong answer should
    # score badly, not raise: a crash tells the run the code is broken, and
    # a low score tells it the answer was poor. They are different lessons.
    print(f"score: {answer}")


if __name__ == "__main__":
    main()
'''

IMPROVE = """\
# What to improve

`solve` takes a list of numbers and returns one. Right now it adds them up.

The score is whatever `score.py` prints. Higher is better.

## What you may change

Only the code between `CADENCE:BEGIN` and `CADENCE:END` in `solve.py`. Keep
the name `solve`, the argument, and a numeric return.

## What you may not change

`score.py`, the problem, or how the score is computed. Standard library only.
"""


def init(
    root: Path = typer.Argument(Path("."), help="Where to write the project."),
) -> None:
    """Write a project that `cadence check` already passes."""
    root.mkdir(parents=True, exist_ok=True)
    name = root.resolve().name
    files = {
        FILENAME: MANIFEST.format(name=name),
        "solve.py": SOLVE,
        "score.py": SCORE,
        "IMPROVE.md": IMPROVE,
    }
    # Nothing is written if anything would be overwritten. A half-written
    # project over someone's work is worse than refusing.
    clashes = sorted(one for one in files if (root / one).exists())
    if clashes:
        die(
            f"{', '.join(clashes)} already there in {root}.",
            "cadence init writes a new project; it will not write over one.",
        )
    for one, body in files.items():
        (root / one).write_text(body)
        found("wrote", str(root / one))
    note(f"\nNow run `cadence check {root}`.")
