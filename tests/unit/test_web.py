"""Which URL means which query, without a socket.

`answer` is a function of (path, params, session factory), so every route can
be checked here and the server below it is left with nothing to test but the
socket. What the JSON says is tests/unit/test_delivery.py's problem; what is
asserted here is that the right query was asked, and that a URL nobody in
this repo typed cannot make it do something else.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from cadence.core.dto import ExperimentSummary, RunDetail, RunSummary, TrialSummary
from cadence.lifecycle.states import RunState, TrialState
from cadence.web.api import HTML, JSON, answer


@contextmanager
def _session():
    yield "a session"


A_RUN = RunSummary(id="r1", status=RunState.FINISHED, trials=3)
A_DETAIL = RunDetail(id="r1", status=RunState.FINISHED, trials=3, scored=2)
A_TRIAL = TrialSummary(
    id="t1", run_id="r1", seq=0, status=TrialState.MEASURED, attempts=1
)


@pytest.fixture
def asked():
    """Every query stubbed, so a route is tested by which one it reached."""
    with (
        patch("cadence.web.api.some_runs", return_value=[A_RUN]) as runs,
        patch("cadence.web.api.some_trials", return_value=[A_TRIAL]) as trials,
        patch("cadence.web.api.run_detail", return_value=A_DETAIL) as run,
        patch("cadence.web.api.trial_detail", return_value=None) as trial,
        patch(
            "cadence.web.api.some_experiments",
            return_value=[ExperimentSummary(name="packing", runs=2)],
        ) as experiments,
    ):
        yield {
            "runs": runs,
            "trials": trials,
            "run": run,
            "trial": trial,
            "experiments": experiments,
        }


def ask(path, **params):
    return answer(path, params, _session)


class TestTheRoutes:
    def test_the_root_is_the_page_itself(self, asked):
        said = ask("/")
        assert said.status == 200
        assert said.content_type == HTML
        assert "<title>cadence</title>" in said.body

    def test_runs_are_listed(self, asked):
        said = ask("/api/runs")
        assert said.content_type == JSON
        assert json.loads(said.body)[0]["id"] == "r1"

    def test_a_run_is_a_detail_not_a_summary(self, asked):
        """The listing and the page ask different questions: one is sized for
        fifty rows, the other pays for the joins."""
        ask("/api/runs/r1")
        assert asked["run"].call_args.args[1] == "r1"
        assert not asked["runs"].called

    def test_the_trials_of_a_run(self, asked):
        ask("/api/runs/r1/trials")
        assert asked["trials"].call_args.args[1] == "r1"

    def test_experiments_are_listed(self, asked):
        assert json.loads(ask("/api/experiments").body)[0]["name"] == "packing"

    def test_filters_are_passed_through(self, asked):
        ask("/api/runs", experiment="packing", owner="ada@lab", status="finished")
        assert asked["runs"].call_args.args[1:4] == ("packing", "ada@lab", "finished")


class TestWhatIsNotThere:
    def test_a_run_nobody_recorded_is_a_404_with_a_sentence(self, asked):
        asked["run"].return_value = None
        said = ask("/api/runs/never-existed")
        assert said.status == 404
        assert "never-existed" in json.loads(said.body)["error"]

    def test_a_path_nobody_serves_is_a_404(self, asked):
        assert ask("/api/nonsense").status == 404

    def test_a_url_outside_the_api_is_not_the_page(self, asked):
        """Only "/" is the page. Anything else falling through to it would
        make every typo look like the dashboard failing to load."""
        assert ask("/../../etc/passwd").status == 404


class TestTheQueryStringIsTheOneInputNobodyHereWrote:
    def test_a_limit_is_obeyed(self, asked):
        ask("/api/runs", limit="7")
        assert asked["runs"].call_args.args[4] == 7

    def test_a_limit_that_is_not_a_number_is_the_default(self, asked):
        ask("/api/runs", limit="all of them")
        assert asked["runs"].call_args.args[4] == 50

    def test_a_limit_nobody_would_wait_for_is_capped(self, asked):
        ask("/api/runs", limit="900000")
        assert asked["runs"].call_args.args[4] == 500

    def test_a_limit_of_zero_still_asks_for_a_row(self, asked):
        ask("/api/runs", limit="0")
        assert asked["runs"].call_args.args[4] == 1


class TestAnIdWithASlashInIt:
    """A trial is identified as "<run id>/<seq>", which is a path separator
    inside a path segment. The page percent-encodes it; the route has to
    split before it unquotes, or one id arrives as two segments."""

    def test_a_trial_is_found_by_its_encoded_id(self, asked):
        ask("/api/trials/20260910-022826-4fda88%2F3")
        assert asked["trial"].call_args.args[1] == "20260910-022826-4fda88/3"

    def test_an_unencoded_one_is_a_404_rather_than_the_wrong_trial(self, asked):
        assert ask("/api/trials/20260910-022826-4fda88/3").status == 404
