import pytest

from cadence.control.judges.cascade import Cascade
from cadence.control.judges.full import Full
from cadence.control.manifest import Plugin
from cadence.control.objectives.ranking import Pareto, WeightedSum
from cadence.control.registry import JUDGES, resolve
from cadence.core.dto import Measurement, RunHistory, TrialResult
from cadence.core.ports import Judge
from cadence.core.verdict import Failed, Outcome, Scored
from cadence.errors import UnknownPlugin


def scored(code, value):
    return TrialResult(
        code=code, verdict=Scored(fingerprint=code, metrics={"value": value})
    )


def history(*values):
    return RunHistory(
        run_id="h1",
        seeds=("seed",),
        results=tuple(scored(f"p{i}", v) for i, v in enumerate(values)),
    )


class Scorer:
    """Gives a quick score on named seeds and a full one otherwise."""

    def __init__(self, quick, full=None):
        self.quick, self.full = quick, full
        self.asked = []

    def __call__(self, code, seeds=None):
        self.asked.append(seeds)
        value = self.full if seeds is None else self.quick
        if value is None:
            verdict = Failed(fingerprint=code, outcome=Outcome.CRASHED, reason="boom")
        else:
            verdict = Scored(fingerprint=code, metrics={"value": value})
        return Measurement(verdict=verdict, wall_ms=0.0, seeds=seeds or (0, 1, 2))


def a_cascade(above=0.5, objective=None):
    return Cascade(objective or WeightedSum(value=1.0), seeds=(0,), above=above)


class TestFull:
    def test_it_is_a_judge(self):
        assert isinstance(Full(), Judge)

    def test_it_measures_once_on_the_runs_seeds(self):
        scorer = Scorer(quick=None, full=3)
        measured = Full().judge("c", history(1), scorer)
        assert scorer.asked == [None]
        assert measured.verdict.metrics == {"value": 3}

    def test_it_is_what_a_manifest_names(self):
        assert JUDGES["full"] is Full


class TestCascade:
    def test_it_is_a_judge(self):
        assert isinstance(a_cascade(), Judge)

    def test_a_promising_quick_score_goes_on_to_the_full_measurement(self):
        scorer = Scorer(quick=5, full=4)
        measured = a_cascade().judge("c", history(1, 2, 3), scorer)
        assert scorer.asked == [(0,), None]
        assert measured.verdict.metrics == {"value": 4}

    def test_a_poor_quick_score_stops_there(self):
        scorer = Scorer(quick=0, full=4)
        measured = a_cascade().judge("c", history(1, 2, 3), scorer)
        assert scorer.asked == [(0,)]
        assert measured.verdict.metrics == {"value": 0}

    def test_the_share_decides_how_good_is_good_enough(self):
        # 2 beats one of three scored programs: enough at a third, not at half.
        assert len(_asked(a_cascade(above=1 / 3), quick=2)) == 2
        assert len(_asked(a_cascade(above=0.5), quick=2)) == 1

    def test_a_quick_failure_is_the_verdict(self):
        scorer = Scorer(quick=None, full=4)
        measured = a_cascade().judge("c", history(1), scorer)
        assert isinstance(measured.verdict, Failed)
        assert scorer.asked == [(0,)]

    def test_with_nothing_to_compare_against_it_measures_in_full(self):
        scorer = Scorer(quick=0, full=4)
        a_cascade().judge("c", history(), scorer)
        assert scorer.asked == [(0,), None]

    def test_incomparable_is_not_worse(self):
        # Under Pareto, one metric up and one down is neither better nor worse.
        objective = Pareto(value=1.0, cost=-1.0)
        past = RunHistory(
            run_id="h1",
            seeds=("seed",),
            results=(
                TrialResult(
                    code="p",
                    verdict=Scored(fingerprint="p", metrics={"value": 1, "cost": 1}),
                ),
            ),
        )
        asked = []

        def measure(code, seeds=None):
            asked.append(seeds)
            metrics = {"value": 2, "cost": 2}
            verdict = Scored(fingerprint=code, metrics=metrics)
            return Measurement(verdict=verdict, wall_ms=0.0)

        a_cascade(above=1.0, objective=objective).judge("c", past, measure)
        assert asked == [(0,), None]


def _asked(cascade, quick):
    scorer = Scorer(quick=quick, full=9)
    cascade.judge("c", history(1, 3, 5), scorer)
    return scorer.asked


class TestCascadeOptions:
    def build(self, **options):
        return resolve(
            "judge",
            JUDGES,
            Plugin(name="cascade", options=options),
            objective=WeightedSum(value=1.0),
        )

    def test_it_needs_seeds(self):
        with pytest.raises(UnknownPlugin, match="at least one seed"):
            self.build(seeds=[])

    def test_the_share_is_between_zero_and_one(self):
        with pytest.raises(UnknownPlugin, match="from 0 to 1"):
            self.build(seeds=[0], above=2)

    def test_a_valid_one_builds(self):
        assert isinstance(self.build(seeds=[0], above=0.25), Cascade)
