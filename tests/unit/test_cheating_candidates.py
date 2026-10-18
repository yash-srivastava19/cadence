"""Candidates that try to score themselves rather than solve the problem.

Each one is a way a search could find a high number without a better program.
The xfails are the holes still open, written down as tests so that closing
one turns it green rather than leaving a claim in the README to check by hand.
The hole they share: in the usual layout score.py imports the candidate, so
the candidate runs inside the scorer's process and owns its stdout.
"""

import textwrap

import pytest

from cadence.control.manifest import Manifest
from cadence.control.model import Model
from cadence.errors import PatchError
from cadence.execution.sandboxes.subprocess import Job, Subprocess
from cadence.parsing.metrics import read

SCORER = textwrap.dedent(
    """\
    from solve import answer
    print(f"score: {answer()}")
    """
)
HONEST = "def answer():\n    return 0.5\n"
IN_PROCESS = pytest.mark.xfail(
    strict=True,
    reason="the candidate runs inside the scorer's process and owns its stdout",
)


def scored(tmp_path, candidate: str) -> float:
    (tmp_path / "score.py").write_text(SCORER)
    (tmp_path / "solve.py").write_text(HONEST)
    (tmp_path / ".cadence").write_text("pick:\n  confirm:\n    seeds: [7, 8]\n")
    job = Job(
        code=candidate,
        program="solve.py",
        command=("python", "score.py"),
        workspace=str(tmp_path),
        seed=0,
        seconds=10.0,
        memory_mb=256,
    )
    execution = Subprocess().run(job)
    return read(execution.stdout, ["score"])["score"]


class TestTheHonestCandidate:
    def test_is_scored_on_what_it_returns(self, tmp_path):
        assert scored(tmp_path, HONEST) == 0.5


class TestACandidateCannotSetItsOwnScore:
    @IN_PROCESS
    def test_by_printing_a_score_and_leaving(self, tmp_path):
        cheat = 'import json, os\nprint(json.dumps({"score": 1e6}))\nos._exit(0)\n'
        assert scored(tmp_path, cheat + HONEST) != 1e6

    @IN_PROCESS
    def test_by_printing_last_on_the_way_out(self, tmp_path):
        cheat = 'import atexit\natexit.register(lambda: print("score: 1000000"))\n'
        assert scored(tmp_path, cheat + HONEST) != 1e6

    @IN_PROCESS
    def test_by_rewriting_what_the_scorer_prints(self, tmp_path):
        cheat = textwrap.dedent(
            """\
            import builtins
            _print = builtins.print
            builtins.print = lambda *a, **k: _print("score: 1000000")
            """
        )
        assert scored(tmp_path, cheat + HONEST) != 1e6


class TestACandidateCannotSeeTheConfirmSeeds:
    def test_the_manifest_is_not_beside_it(self, tmp_path):
        peek = textwrap.dedent(
            """\
            import os
            def answer():
                return 1e6 if os.path.exists(".cadence") else 0.5
            """
        )
        assert scored(tmp_path, peek) == 0.5


class TestADiffStaysInsideTheRegion:
    BEFORE = "fixed = 1\n# CADENCE:BEGIN\nx = 1\n# CADENCE:END\nscore = fixed\n"

    def patch(self, diff: str):
        return Model(backend=object(), template="improve")._patch(
            self.BEFORE, f"```diff\n{diff}```"
        )

    def test_a_change_inside_is_taken(self):
        assert self.patch("--- a\n+++ b\n@@ -3 +3 @@\n-x = 1\n+x = 2\n")

    def test_a_change_outside_is_refused(self):
        with pytest.raises(PatchError, match="outside the marked region"):
            self.patch("--- a\n+++ b\n@@ -5 +5 @@\n-score = fixed\n+score = 1e6\n")


class TestConfirmingNeedsSeedsTheSearchNeverSaw:
    def test_overlapping_seeds_are_refused(self):
        with pytest.raises(ValueError, match="also sandbox seeds"):
            Manifest.model_validate(
                {
                    "api_version": "cadence/v1alpha2",
                    "program": "solve.py",
                    "metrics": {"score": "maximize"},
                    "sandbox": {"seeds": [0, 1]},
                    "pick": {"name": "confirm", "options": {"seeds": [1, 2]}},
                }
            )
