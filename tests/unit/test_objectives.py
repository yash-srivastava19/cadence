import pytest

from cadence.control.objectives.ranking import Pareto, WeightedSum
from cadence.core.ports import Objective
from cadence.errors import MissingMetric


@pytest.fixture(params=["weighted_sum", "pareto"])
def objective(request):
    """Both objectives, ranking value up and weight down."""
    if request.param == "weighted_sum":
        return WeightedSum(value=1.0, weight=-1.0)
    return Pareto(value=1, weight=-1)


class TestAnyObjective:
    """What every objective must do, whichever one it is. A new objective
    inherits this by being added to the fixture above, and cannot quietly
    satisfy less than the others."""

    def test_it_satisfies_the_port(self, objective):
        assert isinstance(objective, Objective)

    def test_nothing_dominates_itself(self, objective):
        metrics = {"value": 2.0, "weight": 1.0}
        assert not objective.dominates(metrics, metrics)

    def test_better_at_everything_wins(self, objective):
        better = {"value": 9.0, "weight": 1.0}
        worse = {"value": 1.0, "weight": 9.0}
        assert objective.dominates(better, worse)
        assert not objective.dominates(worse, better)

    def test_it_says_which_metric_the_verdict_did_not_carry(self, objective):
        with pytest.raises(MissingMetric, match="value"):
            objective.dominates({"weight": 1.0}, {"value": 1.0, "weight": 1.0})

    def test_a_metric_it_was_not_told_about_is_ignored(self, objective):
        better = {"value": 9.0, "weight": 1.0, "noise": 0.0}
        worse = {"value": 1.0, "weight": 9.0, "noise": 99.0}
        assert objective.dominates(better, worse)


class TestWeightedSum:
    def test_a_higher_total_wins(self):
        objective = WeightedSum(value=1.0)
        assert objective.dominates({"value": 2.0}, {"value": 1.0})
        assert not objective.dominates({"value": 1.0}, {"value": 2.0})

    def test_a_negative_weight_turns_a_cost_into_a_gain(self):
        objective = WeightedSum(weight=-1.0)
        assert objective.dominates({"weight": 1.0}, {"weight": 5.0})

    def test_weights_trade_metrics_off(self):
        objective = WeightedSum(value=1.0, weight=-2.0)
        assert objective.dominates(
            {"value": 10.0, "weight": 1.0}, {"value": 9.0, "weight": 1.0}
        )
        assert not objective.dominates(
            {"value": 10.0, "weight": 3.0}, {"value": 9.0, "weight": 1.0}
        )

    def test_a_tie_is_not_domination(self):
        objective = WeightedSum(value=1.0)
        assert not objective.dominates({"value": 1.0}, {"value": 1.0})

    def test_it_ignores_metrics_it_was_not_given_weights_for(self):
        objective = WeightedSum(value=1.0)
        assert objective.dominates(
            {"value": 2.0, "noise": 99.0}, {"value": 1.0, "noise": 0.0}
        )

    def test_a_missing_metric_says_which(self):
        with pytest.raises(MissingMetric, match="value"):
            WeightedSum(value=1.0).dominates({"other": 1.0}, {"value": 1.0})

    def test_it_needs_at_least_one_weight(self):
        with pytest.raises(ValueError, match="at least one weight"):
            WeightedSum()


class TestPareto:
    def test_better_on_every_metric_dominates(self):
        objective = Pareto(value=1, weight=-1)
        assert objective.dominates(
            {"value": 10.0, "weight": 1.0}, {"value": 5.0, "weight": 3.0}
        )

    def test_better_on_one_and_equal_on_the_rest_dominates(self):
        objective = Pareto(value=1, weight=-1)
        assert objective.dominates(
            {"value": 10.0, "weight": 1.0}, {"value": 5.0, "weight": 1.0}
        )

    def test_a_trade_off_is_incomparable(self):
        objective = Pareto(value=1, weight=-1)
        cheap = {"value": 5.0, "weight": 1.0}
        rich = {"value": 10.0, "weight": 9.0}
        assert not objective.dominates(cheap, rich)
        assert not objective.dominates(rich, cheap)

    def test_identical_metrics_do_not_dominate_each_other(self):
        objective = Pareto(value=1)
        assert not objective.dominates({"value": 1.0}, {"value": 1.0})

    def test_a_sense_of_zero_is_refused(self):
        with pytest.raises(ValueError, match="no direction"):
            Pareto(value=0)

    def test_a_missing_metric_says_which(self):
        with pytest.raises(MissingMetric, match="weight"):
            Pareto(value=1, weight=-1).dominates(
                {"value": 1.0}, {"value": 1.0, "weight": 1.0}
            )
