"""What a finished run says, and what it refuses to claim.

The presenters are the only place that knows how output looks. Everything
here is about one question: can a reader compare this run with another one?
"""

import json

from cadence.core.dto import Report, RunSummary, Spend, TrialSummary
from cadence.delivery import (
    as_json,
    as_text,
    one_as_text,
    runs_as_text,
    trials_as_text,
)
from cadence.lifecycle.states import RunState, TrialState


def a_report(**overrides):
    fields = {
        "run_id": "h1",
        "status": RunState.FINISHED,
        "trials": 2,
        "scored": 2,
        "spend": Spend(),
    }
    return Report(**{**fields, **overrides})


class TestWhatARunWasBilled:
    """Tokens are what cadence counts; dollars are what the user is charged.
    They are not the same number and they do not count the same events."""

    def test_a_run_with_no_price_declares_no_bill(self):
        assert Spend().and_also(10, 10, replayed=False).usd is None

    def test_a_priced_call_is_added_up(self):
        spend = Spend().and_also(10, 10, replayed=False, usd=0.25)
        assert spend.and_also(10, 10, replayed=False, usd=0.75).usd == 1.0

    def test_a_replayed_call_is_not_billed_again(self):
        """It was bought once, by the run that recorded it. Charging for it
        again would make a resumed run look more expensive than the one it is
        finishing."""
        spend = Spend().and_also(10, 10, replayed=False, usd=1.0)
        assert spend.and_also(10, 10, replayed=True, usd=1.0).usd == 1.0

    def test_a_replayed_call_still_counts_as_work(self):
        """Calls and tokens describe what it takes to reproduce the run, so
        they count every ask. Only the money is about this run's bill."""
        spend = Spend().and_also(10, 10, replayed=True, usd=1.0)
        assert (spend.calls, spend.replayed, spend.tokens) == (1, 1, 20)

    def test_an_unpriced_call_does_not_zero_a_bill(self):
        spend = Spend().and_also(10, 10, replayed=False, usd=2.0)
        assert spend.and_also(10, 10, replayed=False).usd == 2.0

    def test_free_is_a_bill_and_not_a_silence(self):
        """A local model costs zero, which is a real answer. Reporting it as
        "no price declared" would hide that the run was free."""
        assert Spend().and_also(10, 10, replayed=False, usd=0.0).usd == 0.0


class TestTheTextReport:
    def test_it_says_nothing_about_money_when_nobody_priced_it(self):
        assert "$" not in as_text(a_report())

    def test_it_says_what_the_run_cost_when_it_can(self):
        spend = Spend().and_also(1000, 500, replayed=False, usd=0.0123)
        assert "$0.0123" in as_text(a_report(spend=spend))

    def test_free_is_reported_as_free(self):
        spend = Spend().and_also(10, 10, replayed=False, usd=0.0)
        assert "$0.0000" in as_text(a_report(spend=spend))

    def test_it_says_which_calls_the_bill_covers_when_some_were_replayed(self):
        """Otherwise "3 calls, $0.0021" invites dividing one by the other,
        and the answer is wrong for every run that read an answer back."""
        spend = Spend().and_also(10, 10, replayed=False, usd=0.002)
        spend = spend.and_also(10, 10, replayed=True, usd=0.002)
        assert "for the 1 bought" in as_text(a_report(spend=spend))

    def test_it_still_leads_with_what_was_scored(self):
        assert as_text(a_report()).startswith("finished  2/2 scored")


class TestTheJsonReport:
    def test_the_bill_is_a_field_a_pipe_can_read(self):
        spend = Spend().and_also(10, 10, replayed=False, usd=0.5)
        assert json.loads(as_json(a_report(spend=spend)))["spend"]["usd"] == 0.5

    def test_an_unpriced_run_says_null_rather_than_zero(self):
        assert json.loads(as_json(a_report()))["spend"]["usd"] is None

    def test_both_presenters_are_given_the_same_report(self):
        """Neither is the one the loop knows about."""
        spend = Spend().and_also(10, 10, replayed=False, usd=0.5)
        report = a_report(spend=spend)
        assert json.loads(as_json(report))["spend"]["calls"] == report.spend.calls
        assert str(report.spend.calls) in as_text(report)


class TestAFailedRunIsStillAReport:
    def test_it_carries_the_best_it_found(self):
        report = a_report(
            status=RunState.FAILED,
            scored=1,
            best="abc123",
            program="print(1)",
            metrics={"value": 9.0},
            reason="TerminalModelError: 401",
        )
        assert report.best == "abc123"
        assert "print(1)" in as_text(report)

    def test_it_says_why_it_stopped_before_it_says_what_it_found(self):
        text = as_text(
            a_report(
                status=RunState.FAILED,
                metrics={"value": 9.0},
                reason="TerminalModelError: 401",
            )
        )
        assert text.index("401") < text.index("value = 9")


def a_run(**overrides):
    fields = {"id": "r1", "status": RunState.FINISHED, "trials": 3}
    return RunSummary(**{**fields, **overrides})


def a_trial(**overrides):
    fields = {
        "id": "t1",
        "run_id": "r1",
        "seq": 0,
        "status": TrialState.MEASURED,
        "attempts": 1,
    }
    return TrialSummary(**{**fields, **overrides})


class TestListingRuns:
    def test_an_empty_listing_says_so(self):
        """Rather than printing headers over nothing, which reads like a
        failed query."""
        assert runs_as_text([]) == "no runs"

    def test_it_puts_every_run_on_its_own_line(self):
        text = runs_as_text([a_run(id="r1"), a_run(id="r2")])
        assert len(text.splitlines()) == 4  # header, rule, two runs

    def test_the_columns_line_up(self):
        """The reason to list runs is to compare them, and comparing means
        reading down a column."""
        lines = runs_as_text([a_run(id="short"), a_run(id="a-much-longer-id")])
        assert len({line.index("finished") for line in lines.splitlines()[2:]}) == 1

    def test_a_missing_label_is_not_a_blank(self):
        """An empty cell reads as a column that failed to render."""
        assert "-" in runs_as_text([a_run(experiment=None)])

    def test_it_shows_who_ran_it(self):
        assert "her@lab.edu" in runs_as_text([a_run(owner="her@lab.edu")])

    def test_it_shows_which_question(self):
        assert "cache-eviction" in runs_as_text([a_run(experiment="cache-eviction")])

    def test_a_hash_is_cut_short(self):
        """Fingerprints are 64 characters and no two differ in the last 50.
        Printed whole they push every later column off the screen."""
        assert "f" * 64 not in runs_as_text([a_run(best="f" * 64)])


class TestListingTrials:
    def test_an_empty_listing_says_so(self):
        assert trials_as_text([]) == "no trials"

    def test_it_shows_the_sequence(self):
        assert "7" in trials_as_text([a_trial(seq=7)])

    def test_it_shows_why_one_was_abandoned(self):
        text = trials_as_text(
            [a_trial(status=TrialState.ABANDONED, reason="patch did not apply")]
        )
        assert "patch did not apply" in text


class TestOneRecord:
    def test_it_is_read_down_the_page(self):
        """Nothing to compare it with, so no columns."""
        assert one_as_text(a_run()).count("\n") >= 5

    def test_it_holds_nothing_back(self):
        """`show` is where somebody goes when the listing was not enough."""
        for name in RunSummary.model_fields:
            assert name in one_as_text(a_run())


class TestListingsAreAlsoJson:
    def test_a_list_comes_back_as_an_array(self):
        assert json.loads(as_json([a_run(id="r1"), a_run(id="r2")])) == [
            *[json.loads(as_json(one)) for one in (a_run(id="r1"), a_run(id="r2"))]
        ]

    def test_an_empty_list_is_an_empty_array_not_a_sentence(self):
        """ "no runs" is for a person. A pipe wants something it can iterate."""
        assert json.loads(as_json([])) == []

    def test_one_record_is_an_object(self):
        assert json.loads(as_json(a_run(id="r1")))["id"] == "r1"


class TestATrialShowsWhatItScored:
    """The number somebody is actually watching for. Without it a listing
    says a trial happened and not whether it was any good."""

    def test_the_score_is_there(self):
        assert "0.6183" in trials_as_text([a_trial(metrics={"hit_rate": 0.6183})])

    def test_a_single_metric_prints_bare(self):
        """Naming it in every row costs a column and says nothing new."""
        assert "hit_rate=" not in trials_as_text([a_trial(metrics={"hit_rate": 0.5})])

    def test_several_metrics_are_named(self):
        text = trials_as_text([a_trial(metrics={"speed": 2.0, "size": 3.0})])
        assert "size=3" in text
        assert "speed=2" in text

    def test_a_trial_with_no_score_is_not_a_blank(self):
        """An abandoned trial produced nothing to score, which is a fact
        worth printing rather than an empty cell."""
        assert "-" in trials_as_text([a_trial(metrics=None)])
