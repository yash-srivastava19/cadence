import pytest

from cadence.control.manifest import Plugin
from cadence.control.methods.evolution import Evolution
from cadence.control.objectives.ranking import WeightedSum
from cadence.control.picks.best import Best
from cadence.control.picks.confirm import Confirm
from cadence.control.registry import PICKS, resolve
from cadence.core.dto import RunHistory, TrialResult
from cadence.core.ports import Pick
from cadence.core.verdict import Failed, Outcome, Scored
from cadence.errors import UnknownPlugin
from tests.factories import present


def scored(code, value):
    return TrialResult(
        code=code, verdict=Scored(fingerprint=code, metrics={"value": value})
    )


def history(*results):
    return RunHistory(run_id="h1", seeds=("seed",), results=results)


def never(code, seeds):
    raise AssertionError("best never measures anything")


def a_best():
    objective = WeightedSum(value=1.0)
    return Best(Evolution(objective=objective), objective)


class TestBest:
    def test_it_is_a_pick(self):
        assert isinstance(a_best(), Pick)

    def test_it_is_what_a_manifest_names(self):
        assert PICKS["best"] is Best

    def test_it_names_what_the_method_ranks_first(self):
        picked = present(a_best().pick(history(scored("a", 1), scored("b", 3)), never))
        assert picked.result.code == "b"

    def test_it_names_nothing_when_nothing_scored(self):
        assert a_best().pick(history(), never) is None


class Fresh:
    """Seeds the search never saw, with the numbers they will give."""

    def __init__(self, **scores):
        self.scores = scores
        self.asked = []

    def __call__(self, code, seeds):
        self.asked.append((code, seeds))
        value = self.scores[code]
        if value is None:
            return Failed(fingerprint=code, outcome=Outcome.CRASHED, reason="boom")
        return Scored(fingerprint=code, metrics={"value": value})


def a_confirm(top=3, seeds=(7, 8)):
    objective = WeightedSum(value=1.0)
    return Confirm(Evolution(objective=objective), objective, seeds=seeds, top=top)


SEARCHED = history(scored("a", 1), scored("b", 3), scored("c", 2), scored("d", 0))


class TestConfirm:
    def test_it_is_a_pick(self):
        assert isinstance(a_confirm(), Pick)

    def test_it_measures_the_methods_top_few_on_its_own_seeds(self):
        fresh = Fresh(a=1, b=3, c=2, d=0)
        a_confirm(top=3).pick(SEARCHED, fresh)
        assert fresh.asked == [("b", (7, 8)), ("c", (7, 8)), ("a", (7, 8))]

    def test_the_winner_is_ranked_on_the_fresh_numbers_alone(self):
        # b led the search on a lucky score; on fresh seeds c is better.
        picked = present(a_confirm().pick(SEARCHED, Fresh(a=1, b=1.5, c=2, d=0)))
        assert picked.result.code == "c"
        assert picked.result.metrics == {"value": 2}

    def test_it_keeps_what_the_winner_scored_during_the_search(self):
        picked = present(a_confirm().pick(SEARCHED, Fresh(a=1, b=1.5, c=2, d=0)))
        evidence = present(picked.evidence)
        assert evidence.seeds == (7, 8)
        assert evidence.searched == {"value": 2}
        assert evidence.unconfirmed is None

    def test_a_leader_that_fails_on_fresh_seeds_is_passed_over(self):
        picked = present(a_confirm().pick(SEARCHED, Fresh(a=1, b=None, c=0.5, d=0)))
        assert picked.result.code == "a"

    def test_when_nothing_confirms_it_reports_the_search_best_as_unconfirmed(self):
        picked = present(a_confirm().pick(SEARCHED, Fresh(a=None, b=None, c=None, d=0)))
        assert picked.result.code == "b"
        assert picked.result.metrics == {"value": 3}
        assert "crashed" in present(present(picked.evidence).unconfirmed)

    def test_a_short_history_is_measured_whole(self):
        fresh = Fresh(a=1)
        a_confirm(top=3).pick(history(scored("a", 1)), fresh)
        assert len(fresh.asked) == 1

    def test_it_names_nothing_when_nothing_scored(self):
        assert a_confirm().pick(history(), never) is None


class TestConfirmOptions:
    def manifest_pick(self, **options):
        return Plugin(name="confirm", options=options)

    def test_it_needs_seeds(self):
        objective = WeightedSum(value=1.0)
        with pytest.raises(UnknownPlugin, match="at least one seed"):
            resolve(
                "pick",
                PICKS,
                self.manifest_pick(seeds=[]),
                method=Evolution(objective=objective),
                objective=objective,
            )

    def test_top_must_be_positive(self):
        objective = WeightedSum(value=1.0)
        with pytest.raises(UnknownPlugin, match="top must be at least 1"):
            resolve(
                "pick",
                PICKS,
                self.manifest_pick(seeds=[7], top=0),
                method=Evolution(objective=objective),
                objective=objective,
            )
