from cadence.control.methods.evolution import Evolution
from cadence.control.objectives.ranking import WeightedSum
from cadence.control.picks.best import Best
from cadence.control.registry import PICKS
from cadence.core.dto import RunHistory, TrialResult
from cadence.core.ports import Pick
from cadence.core.verdict import Scored
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
