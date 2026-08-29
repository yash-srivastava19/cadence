import pytest
from pydantic import ValidationError

from cadence.control.entities import Candidate
from cadence.control.methods.evolution import (
    Evolution,
    Measured,
    Unmeasured,
    _rng_for,
)
from cadence.control.model import hint_for
from cadence.control.objectives.ranking import Pareto, WeightedSum
from cadence.core.dto import Directive, RunHistory, TrialBudget, TrialResult
from cadence.core.ports import Method
from cadence.core.verdict import Failed, Outcome, Scored
from cadence.errors import NoCandidates
from tests.factories import as_scored, present

SEED = "def solve(): return []"


def a_verdict(metrics):
    return Scored(fingerprint="fp", metrics=metrics)


def scored(code, value):
    return TrialResult(code=code, verdict=a_verdict({"value": float(value)}))


def crashed(code="x = 1"):
    return TrialResult(
        code=code,
        verdict=Failed(fingerprint="fp", outcome=Outcome.CRASHED, reason="boom"),
    )


def measured(metrics, code="x = 1"):
    return Measured(candidate=Candidate(code=code), verdict=a_verdict(metrics))


def unmeasured(code="x = 1"):
    return Unmeasured(candidate=Candidate(code=code))


def an_evolution(**kwargs):
    return Evolution(objective=WeightedSum(value=1.0), **kwargs)


def past(*results, run_id="h1", seeds=(SEED,)):
    return RunHistory(run_id=run_id, seeds=seeds, results=tuple(results))


def ledger(spent=0, budget=10):
    return TrialBudget(spent=spent, budget=budget)


def drive(method, budget, answers):
    attempts, directives = [], []
    while True:
        got = method.next_directive(past(*attempts), ledger(len(attempts), budget))
        if got is None:
            return directives, attempts
        directives.append(got)
        attempts.append(answers(got, len(directives)))


class TestTheProtocol:
    def test_evolution_satisfies_it(self):
        assert isinstance(an_evolution(), Method)

    def test_it_returns_a_directive(self):
        assert isinstance(an_evolution().next_directive(past(), ledger()), Directive)

    def test_the_first_directive_points_at_a_seed(self):
        assert present(an_evolution().next_directive(past(), ledger())).code == SEED

    def test_a_spent_budget_ends_the_search(self):
        assert an_evolution().next_directive(past(), ledger(spent=10)) is None

    def test_a_budget_of_zero_ends_it_immediately(self):
        assert an_evolution().next_directive(past(), ledger(0, 0)) is None

    def test_it_yields_exactly_the_budget(self):
        directives, _ = drive(an_evolution(), 5, lambda d, n: scored(f"v{n}", n))
        assert len(directives) == 5

    def test_each_trial_is_numbered(self):
        directives, _ = drive(an_evolution(), 4, lambda d, n: scored(f"v{n}", n))
        assert [d.index for d in directives] == [0, 1, 2, 3]

    def test_those_numbers_give_the_model_four_different_hints(self):
        directives, _ = drive(an_evolution(), 4, lambda d, n: scored(f"v{n}", n))
        assert len({hint_for(d.index) for d in directives}) == 4


class TestItIsAPureFunctionOfHistory:
    def test_the_same_history_gives_the_same_directive(self):
        seen = past(scored("v1", 1), scored("v2", 2))
        assert an_evolution().next_directive(
            seen, ledger(2)
        ) == an_evolution().next_directive(seen, ledger(2))

    def test_a_fresh_instance_resumes_where_another_left_off(self):
        directives, attempts = drive(an_evolution(), 4, lambda d, n: scored(f"v{n}", n))
        resumed = an_evolution().next_directive(past(*attempts[:2]), ledger(2))
        assert resumed == directives[2]

    def test_the_same_run_and_trial_draw_the_same_numbers(self):
        assert _rng_for("h1", 3).random() == _rng_for("h1", 3).random()

    def test_a_different_run_draws_different_numbers(self):
        assert _rng_for("a", 0).random() != _rng_for("b", 0).random()

    def test_a_different_trial_draws_different_numbers(self):
        assert _rng_for("h1", 0).random() != _rng_for("h1", 1).random()

    def test_the_method_keeps_no_state_between_calls(self):
        method = an_evolution()
        method.next_directive(past(scored("v1", 9)), ledger(1))
        assert present(method.next_directive(past(), ledger())).code == SEED


class TestTheDirectiveSaysWhatTheParentScored:
    """The method knows what every candidate scored and used to keep it to
    itself, so the model was asked to improve a program without being told
    how that program did. Numbers only: which way is better belongs to the
    manifest, and saying it in English belongs to the prompt."""

    def test_a_scored_parent_hands_over_its_metrics(self):
        history = past(scored("x = 1", 9))
        directive = present(an_evolution().next_directive(history, ledger(1)))
        assert directive.standing == {"value": 9.0}

    def test_a_seed_has_no_standing_rather_than_a_zero(self):
        directive = present(an_evolution().next_directive(past(), ledger()))
        assert directive.standing is None

    def test_it_carries_every_metric_the_verdict_had(self):
        result = TrialResult(
            code="x = 1", verdict=a_verdict({"value": 9.0, "weight": 2.0})
        )
        directive = present(an_evolution().next_directive(past(result), ledger(1)))
        assert directive.standing == {"value": 9.0, "weight": 2.0}

    def test_it_is_the_chosen_parents_score_and_not_the_best_one(self):
        """A tournament does not always pick the leader, and telling the
        model the leader's score while handing it a different program would
        be a lie about the code in front of it."""
        history = past(scored("winner", 100), scored("loser", 1))
        directive = present(
            an_evolution(tournament=1).next_directive(history, ledger(2))
        )
        expected = {"winner": 100.0, "loser": 1.0}[directive.code]
        assert directive.standing == {"value": expected}


class TestAdmission:
    def test_a_scored_child_joins_the_population(self):
        living = an_evolution().population(past(scored("better", 10)))
        assert "better" in [m.candidate.code for m in living]

    def test_a_failed_child_does_not(self):
        living = an_evolution().population(past(crashed()))
        assert [m.candidate.code for m in living] == [SEED]

    def test_the_population_stays_within_its_cap(self):
        seen = tuple(scored(f"v{n}", n) for n in range(1, 11))
        assert len(an_evolution(size=3).population(past(*seen))) == 3

    def test_pruning_keeps_the_strongest(self):
        seen = tuple(scored(f"v{n}", n) for n in range(1, 7))
        best = present(an_evolution(size=2).best(past(*seen)))
        assert as_scored(best.verdict).metrics["value"] == 6.0

    def test_with_nothing_scored_there_is_no_best(self):
        assert an_evolution().best(past(crashed())) is None


class TestTheObjectiveDecides:
    def test_a_weighted_sum_prefers_the_higher_total(self):
        seen = tuple(scored(f"v{n}", n) for n in range(1, 5))
        assert present(an_evolution(size=2).best(past(*seen))).code == "v4"

    def test_pareto_keeps_a_trade_off_that_weighted_sum_would_drop(self):
        cheap = measured({"value": 5.0, "weight": 1.0})
        rich = measured({"value": 10.0, "weight": 9.0})
        pareto = Evolution(objective=Pareto(value=1, weight=-1))
        assert not pareto.better(rich, cheap)
        assert not pareto.better(cheap, rich)

    def test_an_unmeasured_member_never_beats_a_measured_one(self):
        method = an_evolution()
        assert method.better(measured({"value": 1.0}), unmeasured())
        assert not method.better(unmeasured(), measured({"value": 1.0}))


class TestRunningOut:
    def test_a_history_needs_at_least_one_seed(self):
        with pytest.raises(ValidationError, match="at least 1 item"):
            RunHistory(run_id="h1", seeds=())

    def test_a_tournament_needs_an_entrant(self):
        with pytest.raises(ValueError, match="at least one entrant"):
            an_evolution(tournament=0)

    def test_a_population_needs_room(self):
        with pytest.raises(ValueError, match="room for at least one"):
            an_evolution(size=0)

    def test_an_empty_population_says_so(self):
        method = an_evolution()
        method.population = lambda history: []
        with pytest.raises(NoCandidates):
            method.next_directive(past(), ledger())
