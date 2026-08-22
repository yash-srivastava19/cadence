import pytest

from cadence.exceptions import NoCandidates
from cadence.interfaces import Attempt, Directive, Method
from cadence.methods import Evolution, Member
from cadence.objectives import Pareto, WeightedSum
from cadence.verdict import Failed, Outcome, Scored

SEED = "def solve(): return []"


def scored(code, value):
    return Attempt(
        code=code,
        verdict=Scored(fingerprint=f"fp-{value}", metrics={"value": float(value)}),
    )


def crashed(code="x = 1"):
    return Attempt(
        code=code,
        verdict=Failed(fingerprint="fp", outcome=Outcome.CRASHED, reason="boom"),
    )


def a_verdict(metrics):
    return Scored(fingerprint="fp", metrics=metrics)


def an_evolution(**kwargs):
    return Evolution(objective=WeightedSum(value=1.0), **kwargs)


def drive(method, budget, answers):
    search = method.search([SEED], budget)
    directives = []
    reply = None
    while True:
        try:
            directive = search.send(reply)
        except StopIteration:
            return directives
        directives.append(directive)
        reply = answers(directive, len(directives))


class TestTheProtocol:
    def test_evolution_satisfies_it(self):
        assert isinstance(an_evolution(), Method)

    def test_it_yields_directives(self):
        directives = drive(an_evolution(), 2, lambda d, n: scored(f"v{n}", n))
        assert all(isinstance(d, Directive) for d in directives)

    def test_it_yields_exactly_the_budget(self):
        assert len(drive(an_evolution(), 5, lambda d, n: scored(f"v{n}", n))) == 5

    def test_a_budget_of_zero_yields_nothing(self):
        assert drive(an_evolution(), 0, lambda d, n: None) == []

    def test_the_first_directive_points_at_the_seed(self):
        directives = drive(an_evolution(), 1, lambda d, n: None)
        assert directives[0].code == SEED

    def test_hints_vary_between_trials(self):
        directives = drive(an_evolution(), 4, lambda d, n: None)
        assert len({d.hint for d in directives}) == 4


class TestDeterminism:
    def test_the_same_seed_gives_the_same_directives(self):
        answers = lambda d, n: scored(f"v{n}", n)  # noqa: E731
        first = drive(an_evolution(seed=7), 6, answers)
        second = drive(an_evolution(seed=7), 6, answers)
        assert [d.code for d in first] == [d.code for d in second]

    def test_a_different_seed_explores_differently(self):
        answers = lambda d, n: scored(f"v{n}", n)  # noqa: E731
        first = drive(an_evolution(seed=1, size=8), 12, answers)
        second = drive(an_evolution(seed=2, size=8), 12, answers)
        assert [d.code for d in first] != [d.code for d in second]


class TestAdmission:
    def test_a_scored_child_joins_the_population(self):
        method = an_evolution()
        drive(method, 1, lambda d, n: scored("better", 10))
        assert any(m.candidate.code == "better" for m in method.population)

    def test_a_failed_child_does_not(self):
        method = an_evolution()
        drive(method, 1, lambda d, n: crashed())
        assert [m.candidate.code for m in method.population] == [SEED]

    def test_a_failed_child_counts_against_its_parent(self):
        method = an_evolution()
        drive(method, 1, lambda d, n: crashed())
        assert method.population[0].candidate.crashes == 1

    def test_a_child_remembers_its_parent(self):
        method = an_evolution()
        drive(method, 1, lambda d, n: scored("better", 10))
        child = next(m for m in method.population if m.candidate.code == "better")
        assert child.candidate.parent is not None

    def test_the_population_stays_within_its_cap(self):
        method = an_evolution(size=3)
        drive(method, 10, lambda d, n: scored(f"v{n}", n))
        assert len(method.population) == 3

    def test_pruning_keeps_the_strongest(self):
        method = an_evolution(size=2)
        drive(method, 6, lambda d, n: scored(f"v{n}", n))
        assert method.best().verdict.metrics["value"] == 6.0


class TestTheObjectiveDecides:
    def test_a_weighted_sum_prefers_the_higher_total(self):
        method = an_evolution(size=2)
        drive(method, 4, lambda d, n: scored(f"v{n}", n))
        assert method.best().code == "v4"

    def test_pareto_keeps_a_trade_off_that_weighted_sum_would_drop(self):
        cheap = Member(None, a_verdict({"value": 5.0, "weight": 1.0}))
        rich = Member(None, a_verdict({"value": 10.0, "weight": 9.0}))
        pareto = Evolution(objective=Pareto(value=1, weight=-1))
        assert not pareto.better(rich, cheap)
        assert not pareto.better(cheap, rich)

    def test_an_unmeasured_member_never_beats_a_measured_one(self):
        method = an_evolution()
        measured = Member(None, a_verdict({"value": 1.0}))
        fresh = Member(None, None)
        assert method.better(measured, fresh)
        assert not method.better(fresh, measured)


class TestRunningOut:
    def test_a_search_with_no_seeds_says_so(self):
        with pytest.raises(NoCandidates, match="at least one seed"):
            next(an_evolution().search([], 5))

    def test_an_exhausted_budget_stops_rather_than_raising(self):
        search = an_evolution().search([SEED], 1)
        next(search)
        with pytest.raises(StopIteration):
            search.send(scored("v1", 1))

    def test_a_tournament_needs_an_entrant(self):
        with pytest.raises(ValueError):
            an_evolution(tournament=0)

    def test_a_population_needs_room(self):
        with pytest.raises(ValueError):
            an_evolution(size=0)
