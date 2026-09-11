"""Reading runs and trials back, against a real database.

What these check is that the filters filter and the order is the order. The
shape of the answer is tests/unit/test_delivery.py's problem.
"""

import os

import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip(
        "needs TEST_DATABASE_URL; run 'docker compose up -d'", allow_module_level=True
    )

from cadence.control.queries import (
    one_run,
    one_trial,
    run_detail,
    some_experiments,
    some_runs,
    some_trials,
    trial_detail,
)
from cadence.lifecycle.states import RunState, TrialState
from tests.integration.test_journal import (
    CRASHES,
    IMPROVES,
    NONSENSE,
    journalled,
    owner_engine,
    session,
)

__all__ = ["journalled", "owner_engine", "session"]


@pytest.fixture
def three_runs(journalled):
    journalled(IMPROVES, run_id="a", owner="ada@lab", label="packing")
    journalled(IMPROVES, run_id="b", owner="bob@lab", label="packing")
    journalled(IMPROVES, run_id="c", owner="ada@lab", label="caching")


class TestFindingARunAgain:
    def test_everything_is_listed(self, session, three_runs):
        """Counted by id rather than by length: these run against whatever
        else is in the database, which on a developer's machine is whatever
        their last real run left behind."""
        assert {"a", "b", "c"} <= {run.id for run in some_runs(session)}

    def test_by_experiment(self, session, three_runs):
        found = some_runs(session, experiment="packing")
        assert {run.id for run in found} == {"a", "b"}

    def test_by_owner(self, session, three_runs):
        found = some_runs(session, owner="ada@lab")
        assert {run.id for run in found} == {"a", "c"}

    def test_by_both_at_once(self, session, three_runs):
        found = some_runs(session, experiment="packing", owner="ada@lab")
        assert {run.id for run in found} == {"a"}

    def test_by_status(self, session, three_runs):
        finished = {run.id for run in some_runs(session, status=RunState.FINISHED)}
        assert {"a", "b", "c"} <= finished
        failed = {run.id for run in some_runs(session, status=RunState.FAILED)}
        assert not failed & {"a", "b", "c"}

    def test_a_filter_nothing_matches_is_not_an_error(self, session, three_runs):
        """Nobody has run that experiment yet is an answer, not a failure."""
        assert some_runs(session, experiment="nothing-like-this") == []

    def test_limit_is_obeyed(self, session, three_runs):
        assert len(some_runs(session, limit=2)) == 2

    def test_the_newest_comes_first(self, session, three_runs):
        """The run somebody is looking for is nearly always the last one."""
        found = some_runs(session)
        assert found == sorted(found, key=lambda run: run.started_at, reverse=True)


class TestOneRun:
    def test_it_comes_back(self, session, three_runs):
        assert one_run(session, "a").id == "a"

    def test_it_carries_who_and_why(self, session, three_runs):
        found = one_run(session, "a")
        assert (found.owner, found.experiment) == ("ada@lab", "packing")

    def test_a_run_nobody_recorded_is_none_not_an_exception(self, session):
        """The command turns this into "no run called that". A raise here
        would make a typo look like a failure of cadence."""
        assert one_run(session, "never-existed") is None


class TestTheTrialsOfARun:
    @pytest.fixture
    def two_trials(self, journalled):
        journalled(CRASHES, IMPROVES, run_id="a", budget=2)

    def test_only_that_run_s_trials(self, session, two_trials, journalled):
        journalled(IMPROVES, run_id="elsewhere")
        assert all(t.run_id == "a" for t in some_trials(session, "a"))

    def test_in_the_order_they_were_tried(self, session, two_trials):
        """A trial only means anything next to the one before it."""
        assert [t.seq for t in some_trials(session, "a")] == [0, 1]

    def test_by_status(self, session, two_trials):
        found = some_trials(session, "a", status=TrialState.MEASURED)
        assert found
        assert all(t.status == TrialState.MEASURED for t in found)

    def test_a_run_with_no_trials_is_empty_not_missing(self, session):
        assert some_trials(session, "never-existed") == []

    def test_one_trial_comes_back_by_id(self, session, two_trials):
        wanted = some_trials(session, "a")[0]
        assert one_trial(session, wanted.id) == wanted

    def test_a_trial_nobody_recorded_is_none(self, session):
        assert one_trial(session, "never-existed") is None


class TestARunCanBeWatchedWhileItRuns:
    """The two-terminal case: one running a run, one asking how it is going.
    runs.trials is only written when a run ends, so reading that column would
    report 0 for every run somebody actually wants to watch."""

    def test_a_finished_run_counts_its_trials(self, session, journalled):
        journalled(CRASHES, IMPROVES, run_id="done", budget=2)
        assert one_run(session, "done").trials == 2

    def test_a_run_still_going_counts_what_it_has_done(self, session, journalled):
        """Written the way an interrupted run leaves the database: the run row
        says running and still has its starting count of 0."""
        import sqlalchemy as sa

        from cadence.control.storage import runs as runs_table

        journalled(CRASHES, IMPROVES, run_id="live", budget=2)
        session.execute(
            sa.update(runs_table)
            .where(runs_table.c.id == "live")
            .values(status=RunState.RUNNING, trials=0)
        )
        assert one_run(session, "live").trials == 2

    def test_the_listing_agrees_with_the_record(self, session, journalled):
        journalled(IMPROVES, run_id="one", budget=1)
        [found] = [run for run in some_runs(session) if run.id == "one"]
        assert found.trials == one_run(session, "one").trials


class TestATrialCarriesItsScore:
    """Reached through the candidate the trial produced. The listing is the
    place somebody looks to see whether anything is improving."""

    def test_a_measured_trial_has_its_metrics(self, session, journalled):
        journalled(IMPROVES, run_id="scored", budget=1)
        [trial] = some_trials(session, "scored")
        assert trial.metrics
        assert "value" in trial.metrics

    def test_it_says_the_outcome(self, session, journalled):
        journalled(IMPROVES, run_id="scored", budget=1)
        assert some_trials(session, "scored")[0].outcome == "scored"

    def test_a_crashing_candidate_says_so_instead_of_a_score(self, session, journalled):
        journalled(CRASHES, run_id="broke", budget=1)
        [trial] = some_trials(session, "broke")
        assert trial.outcome == "crashed"
        assert trial.metrics is None

    def test_a_trial_that_made_nothing_has_no_verdict(self, session, journalled):
        """The model answered with prose, so no patch applied and there is no
        candidate to have scored. An outer join, or the trial would vanish."""
        journalled(NONSENSE, run_id="nothing", budget=1)
        [trial] = some_trials(session, "nothing")
        assert (trial.candidate, trial.outcome, trial.metrics) == (None, None, None)

    def test_one_trial_looked_up_by_id_carries_it_too(self, session, journalled):
        journalled(IMPROVES, run_id="scored", budget=1)
        wanted = some_trials(session, "scored")[0]
        assert one_trial(session, wanted.id).metrics == wanted.metrics


class TestARunPageCanAffordMoreThanAListing:
    """What a fifty-row listing will not pay for: what the run spent, how
    long it took, and what it was started from."""

    def test_it_is_still_a_run_summary(self, session, journalled):
        journalled(IMPROVES, run_id="detail", budget=1)
        assert run_detail(session, "detail").id == one_run(session, "detail").id

    def test_it_counts_the_work_the_run_asked_for(self, session, journalled):
        journalled(IMPROVES, run_id="bought", budget=1)
        spend = run_detail(session, "bought").spend
        assert (spend.calls, spend.replayed) == (1, 0)
        assert spend.tokens_in > 0

    def test_an_unpriced_provider_spends_nothing_nameable(self, session, journalled):
        """None, not zero. Nobody declared a price for the scripted backend,
        and $0.00 would be a lie with a decimal point on it."""
        journalled(IMPROVES, run_id="unpriced", budget=1)
        assert run_detail(session, "unpriced").spend.usd is None

    def test_it_counts_the_trials_that_came_back_with_a_score(
        self, session, journalled
    ):
        journalled(CRASHES, IMPROVES, run_id="some-scored", budget=2)
        found = run_detail(session, "some-scored")
        assert (found.trials, found.scored) == (2, 1)

    def test_it_took_some_time(self, session, journalled):
        """From the first fact to the last. runs has no finished_at, and a
        killed process would never have written one anyway."""
        journalled(IMPROVES, run_id="timed", budget=1)
        assert run_detail(session, "timed").duration_ms >= 0

    def test_a_replay_is_work_but_not_a_bill(self, session, journalled):
        """Spend says these two count differently and they have to keep
        doing it: reproducing the run means making the call again, and a
        reply read back out of the database was not bought twice."""
        import sqlalchemy as sa

        from cadence.control.storage import events

        journalled(IMPROVES, run_id="replaying", budget=1)
        session.execute(
            sa.update(events)
            .where(
                sa.and_(events.c.run_id == "replaying", events.c.type == "ModelCalled")
            )
            .values(payload=events.c.payload.concat({"replayed": True}))
        )
        spend = run_detail(session, "replaying").spend
        assert (spend.calls, spend.replayed) == (1, 1)

    def test_it_carries_the_manifest_it_was_started_from(self, session, journalled):
        """The point of a run page is "what was I even trying", and a hash
        cannot answer that."""
        journalled(IMPROVES, run_id="configured", budget=1)
        assert run_detail(session, "configured").manifest

    def test_a_run_nobody_recorded_is_none(self, session):
        assert run_detail(session, "never-existed") is None


class TestATrialPageShowsWhatChanged:
    def test_it_is_still_a_trial_summary(self, session, journalled):
        journalled(IMPROVES, run_id="one-trial", budget=1)
        wanted = some_trials(session, "one-trial")[0]
        assert trial_detail(session, wanted.id).seq == wanted.seq

    def test_the_diff_is_against_the_parent(self, session, journalled):
        journalled(IMPROVES, run_id="changed", budget=1)
        wanted = some_trials(session, "changed")[0]
        diff = trial_detail(session, wanted.id).diff
        assert diff.startswith("--- parent")
        assert any(line.startswith("+") for line in diff.splitlines())

    def test_a_trial_that_made_nothing_has_no_diff_rather_than_an_empty_one(
        self, session, journalled
    ):
        """None and "" are different answers: one trial produced nothing to
        compare, the other produced something identical to its parent."""
        journalled(NONSENSE, run_id="made-nothing", budget=1)
        wanted = some_trials(session, "made-nothing")[0]
        assert trial_detail(session, wanted.id).diff is None

    def test_it_says_what_the_model_call_cost(self, session, journalled):
        journalled(IMPROVES, run_id="billed", budget=1)
        wanted = some_trials(session, "billed")[0]
        assert trial_detail(session, wanted.id).model

    def test_it_carries_what_the_model_actually_said(self, session, journalled):
        """The diff can only show what survived parsing. When a patch would
        not apply, this is the only place that says why."""
        journalled(NONSENSE, run_id="prose", budget=1)
        wanted = some_trials(session, "prose")[0]
        assert trial_detail(session, wanted.id).response

    def test_it_says_how_long_measuring_took(self, session, journalled):
        journalled(IMPROVES, run_id="measured", budget=1)
        wanted = some_trials(session, "measured")[0]
        assert trial_detail(session, wanted.id).wall_ms >= 0

    def test_a_retry_that_never_came_back_does_not_hide_the_answer(
        self, session, journalled
    ):
        """A trial written before a call and killed mid-request leaves an
        unanswered row that sorts last. Joining to it would report a trial as
        having said nothing, with the reply it used in the row before."""
        import sqlalchemy as sa

        from cadence.control.storage import model_calls

        journalled(IMPROVES, run_id="interrupted", budget=1)
        wanted = some_trials(session, "interrupted")[0]
        answered = trial_detail(session, wanted.id)
        # Written the way the journal writes one: before the call, with
        # nothing back yet, and sorting after the call that was answered.
        was = (
            session.execute(
                sa.select(model_calls).where(model_calls.c.trial_id == wanted.id)
            )
            .mappings()
            .first()
        )
        session.execute(
            sa.insert(model_calls).values(
                {
                    **was,
                    "id": was["id"] + "#never",
                    "status": "in_flight",
                    "response": None,
                    "model": None,
                    "occurred_at": sa.func.now(),
                }
            )
        )
        assert trial_detail(session, wanted.id).response == answered.response

    def test_a_trial_nobody_recorded_is_none(self, session):
        assert trial_detail(session, "never-existed") is None


class TestExperimentsAreDerivedNotStored:
    """There is no experiments table. `experiment` is a column runs copy off
    their manifest, so this is a GROUP BY with a name."""

    def test_runs_are_gathered_under_their_name(self, session, three_runs):
        found = {e.name: e for e in some_experiments(session)}
        assert found["packing"].runs == 2
        assert found["caching"].runs == 1

    def test_a_run_that_named_nothing_is_left_out(self, session, journalled):
        """ "" is not an experiment, it is the absence of one, and a row for
        it would sort into the middle of a list of real ones."""
        journalled(IMPROVES, run_id="anonymous", budget=1)
        assert all(e.name for e in some_experiments(session))

    def test_it_shows_the_most_recent_best(self, session, three_runs):
        found = {e.name: e for e in some_experiments(session)}
        assert found["packing"].best

    def test_the_busiest_experiment_is_not_the_first_one(self, session, three_runs):
        """Ordered by when it last did something. An experiment nobody has
        touched in a month does not belong at the top."""
        found = some_experiments(session)
        assert found == sorted(found, key=lambda e: e.last_activity, reverse=True)
