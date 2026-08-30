"""The commands against a real database, through the CLI a user types.

Everything else mocks something. This runs `cadence run`, then asks
`cadence runs list` what happened, and the only thing joining the two is the
database -- which is the arrangement a person actually has.
"""

import json
import os
from uuid import uuid4

import pytest

URL = os.environ.get("TEST_DATABASE_URL")

if not URL:
    pytest.skip(
        "needs TEST_DATABASE_URL; run 'docker compose up -d'", allow_module_level=True
    )

from typer.testing import CliRunner  # noqa: E402

from cadence.commands import app  # noqa: E402

runner = CliRunner()

PROGRAM = "# CADENCE:BEGIN\nprint('value: 1')\n# CADENCE:END\n"
MANIFEST = """\
api_version: cadence/v1alpha2
program: prog.py
experiment: {label}
metrics:
  value: maximize
budget:
  trials: 1
"""


@pytest.fixture
def label():
    """These commands open their own session and really commit, so the
    transactional fixture the other integration tests use does not reach
    them. A label nobody else uses is what keeps one test out of another."""
    made = f"packing-{uuid4().hex[:8]}"
    yield made
    _forget(made)


def _forget(label):
    """Runs recorded under this label, and everything hanging off them."""
    import sqlalchemy as sa

    from cadence.control.storage import (
        candidates,
        engine,
        events,
        model_calls,
        runs,
        trials,
    )

    bound = engine(URL)
    with bound.begin() as connection:
        mine = sa.select(runs.c.id).where(runs.c.experiment == label).scalar_subquery()
        # Children before parents: model_calls points at trials, and
        # trials and candidates both point at runs.
        for table in (model_calls, events, trials, candidates):
            connection.execute(sa.delete(table).where(table.c.run_id.in_(mine)))
        connection.execute(sa.delete(runs).where(runs.c.experiment == label))
    bound.dispose()


@pytest.fixture
def project(tmp_path, monkeypatch, label):
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("CADENCE_OWNER", "ada@lab")
    (tmp_path / "prog.py").write_text(PROGRAM)
    (tmp_path / ".cadence").write_text(MANIFEST.format(label=label))
    return tmp_path


def a_run(project, *args):
    """Start a run and let it end however it ends.

    With no provider configured the scripted backend runs out of answers and
    the run fails, which is fine here: a run that failed is still a run, and
    what these tests are about is whether it can be found again afterwards.
    """
    result = runner.invoke(app, ["run", str(project), *args])
    assert "Traceback" not in result.output, result.output
    return result


def listed(label, *args):
    result = runner.invoke(
        app, ["runs", "list", "--json", "--experiment", label, *args]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


class TestARunCanBeFoundAfterwards:
    def test_it_shows_up_in_the_listing(self, project, label):
        a_run(project)
        assert len(listed(label)) == 1

    def test_it_carries_who_ran_it(self, project, label):
        a_run(project)
        [found] = listed(label, "--owner", "ada@lab")
        assert found["owner"] == "ada@lab"

    def test_a_run_that_failed_is_recorded_too(self, project, label):
        """The run these tests make has no provider, so it fails -- and it
        still has to be findable. A run you cannot look up is the one you
        most want to."""
        a_run(project)
        [found] = listed(label)
        assert found["status"] == "failed"
        assert found["reason"]

    def test_mine_finds_it_without_being_told_who_that_is(self, project, label):
        a_run(project)
        result = runner.invoke(
            app, ["runs", "list", "--mine", "--experiment", label, "--json"]
        )
        assert [run["owner"] for run in json.loads(result.output)] == ["ada@lab"]

    def test_the_trials_can_be_listed(self, project, label):
        a_run(project)
        run_id = listed(label)[0]["id"]
        result = runner.invoke(app, ["trials", "list", "--run", run_id, "--json"])
        assert result.exit_code == 0, result.output
        assert [t["run_id"] for t in json.loads(result.output)] == [run_id]

    def test_one_run_can_be_shown_in_full(self, project, label):
        a_run(project)
        run_id = listed(label)[0]["id"]
        result = runner.invoke(app, ["runs", "show", run_id, "--json"])
        assert json.loads(result.output)["id"] == run_id

    def test_a_run_nobody_recorded_exits_one(self, project, label):
        result = runner.invoke(app, ["runs", "show", "no-such-run"])
        assert result.exit_code == 1
        assert "no-such-run" in result.output


class TestEachRunGetsItsOwnName:
    def test_two_runs_of_one_project_are_two_runs(self, project, label):
        """The old default named every run "local", so this was one run
        resumed -- and on a shared database, somebody else's."""
        a_run(project)
        a_run(project)
        assert len({run["id"] for run in listed(label)}) == 2

    def test_reusing_a_name_is_refused(self, project, label):
        a_run(project, "--id", "taken")
        result = runner.invoke(app, ["run", str(project), "--id", "taken"])
        assert result.exit_code == 1
        assert "already recorded" in result.output

    def test_it_says_how_to_carry_the_run_on_instead(self, project, label):
        a_run(project, "--id", "taken")
        result = runner.invoke(app, ["run", str(project), "--id", "taken"])
        assert "--resume taken" in result.output

    def test_resuming_a_run_nobody_recorded_is_refused(self, project, label):
        result = runner.invoke(app, ["run", str(project), "--resume", "never-ran"])
        assert result.exit_code == 1
        assert "never-ran" in result.output


class TestOutputSuitsWhoIsReading:
    def test_a_pipe_gets_json(self, project, label):
        """CliRunner is never a terminal, which is exactly the case that
        matters: a script, a log, a CI job."""
        a_run(project)
        json.loads(runner.invoke(app, ["runs", "list"]).output)

    def test_a_terminal_gets_a_table(self, project, label, monkeypatch):
        a_run(project)
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert "experiment" in runner.invoke(app, ["runs", "list"]).output

    def test_json_can_be_asked_for_anyway(self, project, label, monkeypatch):
        a_run(project)
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        json.loads(runner.invoke(app, ["runs", "list", "--json"]).output)
