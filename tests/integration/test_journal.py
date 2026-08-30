"""A real run, against a real database.

The point of these is not that rows appear. It is that what the database says
afterwards is what actually happened -- read back without looking at any of
the objects the run used.
"""

import os

import pytest

OWNER = os.environ.get("TEST_DATABASE_URL")

if not OWNER:
    pytest.skip(
        "needs TEST_DATABASE_URL; run 'docker compose up -d'", allow_module_level=True
    )

sa = pytest.importorskip("sqlalchemy", reason="run 'pip install -e .'")

from sqlalchemy import orm  # noqa: E402

from cadence.control.experiment import Experiment  # noqa: E402
from cadence.control.journal import Journal  # noqa: E402
from cadence.control.methods.evolution import Evolution  # noqa: E402
from cadence.control.model import Model  # noqa: E402
from cadence.control.objectives.ranking import WeightedSum  # noqa: E402
from cadence.control.storage import (  # noqa: E402
    blobs,
    candidates,
    engine,
    events,
    model_calls,
    runs,
    templates,
    trials,
    verdicts,
)
from cadence.core.identity import fingerprint  # noqa: E402
from cadence.core.verdict import Outcome  # noqa: E402
from cadence.execution.runner import TrialRunner  # noqa: E402
from cadence.execution.sandboxes.subprocess import Subprocess  # noqa: E402
from cadence.lifecycle.states import (  # noqa: E402
    CandidateState,
    RunState,
    TrialState,
)
from cadence.observe.signals import cadence  # noqa: E402
from tests.factories import BASELINE, a_manifest  # noqa: E402

IMPROVES = "Here it is.\n```python\nprint('value: 45')\n```"
IMPROVES_MORE = "Better.\n```python\nprint('value: 99')\n```"
CRASHES = "Try this.\n```python\nraise ValueError('the evolved code is broken')\n```"
NONSENSE = "I would change the loop, but here is prose instead."


@pytest.fixture(scope="module")
def owner_engine():
    made = engine(OWNER)
    yield made
    made.dispose()


@pytest.fixture
def session(owner_engine):
    """Rails' transactional fixtures: the run may commit, and none of it
    survives the test."""
    connection = owner_engine.connect()
    outer = connection.begin()
    session = orm.Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def journalled(session):
    """A run that writes itself down. Returns a function that runs it."""
    journal = Journal(session)
    stop = cadence.record(journal.record)

    def run(*responses, run_id="h1", budget=1, backend=None, owner=None, label=None):
        from cadence.control.backends import Scripted

        experiment = Experiment(
            run_id=run_id,
            owner=owner,
            experiment=label,
            manifest=a_manifest(),
            method=Evolution(objective=WeightedSum(value=1.0)),
            model=Model(backend=backend or Scripted(*responses)),
            runner=TrialRunner(
                program="prog.py",
                command=("python", "prog.py"),
                metrics={"value": "maximize"},
                sandbox=Subprocess(),
                seeds=(0,),
            ),
            seeds=[BASELINE],
            budget=budget,
        )
        return experiment.run()

    yield run
    stop()


def rows(session, table, **where):
    statement = sa.select(table)
    for column, value in where.items():
        statement = statement.where(table.c[column] == value)
    return session.execute(statement.order_by(*table.primary_key)).mappings().all()


class TestAFinishedRunWroteItselfDown:
    def test_the_run_is_there(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, runs, id="h1")) == 1

    def test_it_says_the_run_finished(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["status"] == RunState.FINISHED

    def test_it_counted_the_trials(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["trials"] == 1

    def test_it_names_the_best_candidate(self, session, journalled):
        report = journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["best"] == report.best

    def test_it_remembers_which_manifest_produced_it(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, runs, id="h1")[0]["manifest_hash"] == a_manifest().hash


class TestAFailedRunIsStillWrittenDown:
    """A run that stopped badly is the one somebody comes back to read. If
    the row says it found nothing while verdicts holds a score, the database
    and the report are two accounts of the same run."""

    def _ran_out(self, journalled):
        # One answer, two trials: the second ask finds the backend empty.
        return journalled(IMPROVES, budget=2)

    def test_the_row_says_it_failed(self, session, journalled):
        self._ran_out(journalled)
        assert rows(session, runs, id="h1")[0]["status"] == RunState.FAILED

    def test_the_row_names_the_best_it_found(self, session, journalled):
        report = self._ran_out(journalled)
        assert rows(session, runs, id="h1")[0]["best"] == report.best
        assert report.best is not None

    def test_the_verdict_it_earned_is_still_there(self, session, journalled):
        self._ran_out(journalled)
        assert len(rows(session, verdicts)) == 1

    def test_the_row_says_why_it_stopped(self, session, journalled):
        self._ran_out(journalled)
        assert "ran out of responses" in rows(session, runs, id="h1")[0]["reason"]


class TestTheTapeIsTheWholeRun:
    def test_every_fact_was_written(self, session, journalled):
        journalled(IMPROVES)
        assert [row["type"] for row in rows(session, events, run_id="h1")] == [
            "RunStarted",
            "TrialStarted",
            "ModelRequested",
            "ModelCalled",
            "ProposalReceived",
            "CandidateBuilt",
            "TrialMeasured",
            "RunFinished",
        ]

    def test_the_tape_is_numbered_from_zero(self, session, journalled):
        journalled(IMPROVES)
        assert [row["seq"] for row in rows(session, events, run_id="h1")] == list(
            range(8)
        )

    def test_a_fact_carries_what_it_was_about(self, session, journalled):
        journalled(IMPROVES)
        measured = [
            row
            for row in rows(session, events, run_id="h1")
            if row["type"] == "TrialMeasured"
        ]
        assert measured[0]["payload"]["verdict"]["metrics"] == {"value": 45.0}

    def test_it_keeps_both_clocks(self, session, journalled):
        journalled(IMPROVES)
        row = rows(session, events, run_id="h1")[0]
        assert row["occurred_at"] <= row["recorded_at"]

    def test_the_run_id_is_a_column_not_a_payload_field(self, session, journalled):
        journalled(IMPROVES)
        assert "run_id" not in rows(session, events, run_id="h1")[0]["payload"]


class TestARunThatFailed:
    def test_it_is_recorded_as_failed(self, session, journalled):
        journalled(run_id="h2")  # no scripted answers at all
        assert rows(session, runs, id="h2")[0]["status"] == RunState.FAILED

    def test_it_says_why(self, session, journalled):
        journalled(run_id="h2")
        assert "ran out of responses" in rows(session, runs, id="h2")[0]["reason"]

    def test_the_tape_still_ends_with_the_run_finishing(self, session, journalled):
        journalled(run_id="h2")
        assert rows(session, events, run_id="h2")[-1]["type"] == "RunFinished"


class TestTheCandidatesAreThere:
    def test_the_seed_and_the_child_are_both_candidates(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, candidates, run_id="h1")) == 2

    def test_the_child_points_back_at_the_seed(self, session, journalled):
        journalled(IMPROVES)
        child = next(
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        )
        assert child["parent_id"].endswith(fingerprint(BASELINE))

    def test_the_source_is_stored_once_and_pointed_at(self, session, journalled):
        report = journalled(IMPROVES)
        best = next(
            row
            for row in rows(session, candidates, run_id="h1")
            if row["fingerprint"] == report.best
        )
        body = session.execute(
            sa.select(blobs.c.body).where(blobs.c.hash == best["code_hash"])
        ).scalar()
        assert body == report.program

    def test_a_program_proposed_twice_is_stored_once(self, session, journalled):
        """Content-addressed. A 500-trial run would otherwise store the same
        program hundreds of times."""
        journalled(IMPROVES, IMPROVES, budget=2)
        bodies = session.execute(sa.select(blobs.c.body)).scalars().all()
        assert len(bodies) == len(set(bodies))


class TestTheTrialsAreThere:
    def test_the_trial_is_recorded(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, trials, run_id="h1")) == 1

    def test_it_ends_measured(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["status"] == TrialState.MEASURED

    def test_its_seq_is_the_one_the_tape_used(self, session, journalled):
        journalled(IMPROVES)
        started = next(
            row
            for row in rows(session, events, run_id="h1")
            if row["type"] == "TrialStarted"
        )
        assert rows(session, trials, run_id="h1")[0]["seq"] == started["payload"]["seq"]

    def test_it_remembers_which_candidate_it_started_from(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["parent_fingerprint"] == (
            fingerprint(BASELINE)
        )


class TestATrialThatWasAskedAgain:
    def test_the_retries_are_counted(self, session, journalled):
        journalled(NONSENSE, IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["attempts"] == 1

    def test_a_retry_is_not_a_second_trial(self, session, journalled):
        journalled(NONSENSE, IMPROVES)
        assert len(rows(session, trials, run_id="h1")) == 1

    def test_the_tape_says_it_was_retried_rather_than_rejected(
        self, session, journalled
    ):
        """Two different things that used to be one fact: a retry costs a
        model call, a rejection ends the trial."""
        journalled(NONSENSE, IMPROVES)
        assert "TrialRetried" in [
            row["type"] for row in rows(session, events, run_id="h1")
        ]


class TestWhatTheCallCost:
    """The row is where a run's bill lives, so score-per-dollar has somewhere
    to be computed from later. Recorded through a real provider backend --
    the price is applied where the tokens are counted, and nothing between
    there and the database is allowed to drop it."""

    def _priced(self, session, prices):
        from cadence.control.backends import chat_backend
        from tests.unit.test_backends import Recorded, spoke

        return chat_backend(
            "gemini",
            key="x",
            prices=prices,
            http=Recorded(
                spoke(IMPROVES, tokens_in=1_000_000, tokens_out=0, model="m")
            ),
        )

    def test_a_priced_call_is_written_down_in_dollars(self, session, journalled):
        journalled(backend=self._priced(session, {"m": {"in": 4.0, "out": 0.0}}))
        assert float(rows(session, model_calls)[0]["cost_usd"]) == 4.0

    def test_an_unpriced_call_records_no_amount(self, session, journalled):
        """Null, not zero. The column has to be able to say "nobody told us",
        or every unpriced run looks free."""
        journalled(backend=self._priced(session, {}))
        assert rows(session, model_calls)[0]["cost_usd"] is None

    def test_the_report_and_the_row_agree(self, session, journalled):
        report = journalled(
            backend=self._priced(session, {"m": {"in": 4.0, "out": 0.0}})
        )
        assert float(rows(session, model_calls)[0]["cost_usd"]) == report.spend.usd


class TestThePromptTemplateIsKept:
    """The recipe names the template; the body is in code that changes. A run
    replayed after an edit would rebuild a different prompt."""

    def test_the_template_is_stored_by_content(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, templates)) == 1

    def test_the_call_points_at_it(self, session, journalled):
        journalled(IMPROVES)
        stored = rows(session, templates)[0]
        assert rows(session, model_calls)[0]["template_hash"] == stored["hash"]

    def test_the_body_is_the_one_that_was_rendered(self, session, journalled):
        from cadence.control.model import TEMPLATES

        journalled(IMPROVES)
        stored = rows(session, templates)[0]
        assert stored["body"] == TEMPLATES[stored["name"]]

    def test_two_calls_from_one_template_store_it_once(self, session, journalled):
        journalled(NONSENSE, IMPROVES)
        assert len(rows(session, model_calls)) == 2
        assert len(rows(session, templates)) == 1


class TestEveryCallWeMadeIsClosed:
    """A model_calls row is written in_flight before the call and closed by
    the answer. One left open means "we may have paid for this and never saw
    the reply", which is a thing only a crash should be able to produce.

    Closing it after parsing instead left every retry open: the call was made
    and billed, the reply merely did not parse, and the database recorded it
    as a call that may never have happened.
    """

    def _statuses(self, session, run_id="h1"):
        return [row["status"] for row in rows(session, model_calls, run_id=run_id)]

    def test_a_reply_that_did_not_parse_is_still_a_call_that_happened(
        self, session, journalled
    ):
        journalled(NONSENSE, IMPROVES)
        assert self._statuses(session) == ["done", "done"]

    def test_a_trial_given_up_on_leaves_nothing_open(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert set(self._statuses(session)) == {"done"}

    def test_the_unusable_reply_is_kept_with_the_call(self, session, journalled):
        """So a resumed run replays it rather than buying the same prose
        again, and so a person can see what the model actually said."""
        journalled(NONSENSE, IMPROVES)
        assert rows(session, model_calls, run_id="h1")[0]["response"] == NONSENSE

    def test_a_call_that_never_answered_stays_open(self, session, journalled):
        """The other half of the pairing. A terminal error before any reply
        is exactly the case the in_flight row exists to record."""
        from cadence.errors import TerminalModelError

        journalled(TerminalModelError("401"))
        assert self._statuses(session) == ["in_flight"]


class TestATrialThatWasGivenUpOn:
    def test_it_ends_abandoned(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert rows(session, trials, run_id="h1")[0]["status"] == TrialState.ABANDONED

    def test_it_says_why(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        assert "```python block" in rows(session, trials, run_id="h1")[0]["reason"]

    def test_it_built_no_candidate(self, session, journalled):
        journalled(*[NONSENSE] * 4)
        children = [
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        ]
        assert children == []


class TestWhatEachCandidateScored:
    def test_the_verdict_is_recorded(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, verdicts)) == 1

    def test_it_carries_the_metrics(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, verdicts)[0]["metrics"] == {"value": 45.0}

    def test_it_is_keyed_on_the_candidate_that_was_measured(self, session, journalled):
        report = journalled(IMPROVES)
        assert rows(session, verdicts)[0]["candidate_hash"] == report.best

    def test_it_says_which_task_it_was_measured_against(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, verdicts)[0]["task_hash"]

    def test_it_says_which_seeds_it_was_measured_on(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, verdicts)[0]["seeds_hash"]

    def test_a_failure_is_recorded_with_its_reason_and_no_metrics(
        self, session, journalled
    ):
        journalled(CRASHES)
        row = rows(session, verdicts)[0]
        assert (row["outcome"], row["metrics"]) == (Outcome.CRASHED, None)


class TestTheSameMeasurementTwice:
    def test_measuring_one_program_twice_writes_one_row(self, session, journalled):
        """The key is the measurement, not the attempt. Two trials that
        propose the same program against the same task on the same seeds have
        measured the same thing."""
        journalled(IMPROVES, IMPROVES, budget=2)
        assert len(rows(session, verdicts)) == 1

    def test_two_different_programs_are_two_measurements(self, session, journalled):
        journalled(IMPROVES, IMPROVES_MORE, budget=2)
        assert len(rows(session, verdicts)) == 2


class TestTheCallWeWereAboutToMake:
    """Every other step of a trial happens inside our own process, where
    dying means it either committed or it did not. A model call is the one
    step where dying leaves the question open."""

    def test_the_request_is_written_down(self, session, journalled):
        journalled(IMPROVES)
        assert len(rows(session, model_calls)) == 1

    def test_it_ends_up_marked_done(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, model_calls)[0]["status"] == "done"

    def test_it_keeps_the_recipe_that_rebuilds_the_prompt(self, session, journalled):
        journalled(IMPROVES)
        recipe = rows(session, model_calls)[0]["recipe"]
        assert set(recipe) == {
            "template",
            "code",
            "standing",
            "problem",
            "hint",
            "guidance",
        }

    def test_the_stored_recipe_really_does_rebuild_it(self, session, journalled):
        """Not the key names -- the prompt itself, against the digest of the
        one that was sent. Replay is only sound if the row can reproduce the
        question exactly, so anything new the prompt is built from has to be
        in the recipe or the reproduction quietly drifts."""
        from cadence.control.model import render
        from cadence.control.recall import digest

        journalled(IMPROVES)
        row = rows(session, model_calls)[0]
        assert digest(render(row["recipe"])) == row["request_hash"]

    def test_it_rebuilds_a_retry_too(self, session, journalled):
        """The attempt that carries what went wrong is the one most likely to
        be left out of the recipe, because it comes from the loop rather than
        from the directive."""
        from cadence.control.model import render
        from cadence.control.recall import digest

        journalled(NONSENSE, IMPROVES)
        retried = rows(session, model_calls)[1]
        assert digest(render(retried["recipe"])) == retried["request_hash"]
        assert "could not be used" in render(retried["recipe"])

    def test_it_counts_what_the_call_cost(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, model_calls)[0]["tokens_out"] > 0

    def test_it_belongs_to_the_trial_that_asked(self, session, journalled):
        journalled(IMPROVES)
        assert rows(session, model_calls)[0]["trial_id"] == "h1/0"

    def test_a_retry_is_a_second_call_with_its_own_row(self, session, journalled):
        """Deliberately not the same key: a retry asks a different question --
        the same program plus what was wrong with the last reply -- and must
        not replay the answer that already failed to parse."""
        journalled(NONSENSE, IMPROVES)
        assert len(rows(session, model_calls)) == 2

    def test_the_recipe_is_not_also_on_the_tape(self, session, journalled):
        """It holds the whole parent program, and events is the one table
        nobody may prune."""
        journalled(IMPROVES)
        asked = next(
            row
            for row in rows(session, events, run_id="h1")
            if row["type"] == "ModelRequested"
        )
        assert "recipe" not in asked["payload"]


class TestATrialSaysWhatItProduced:
    def test_a_measured_trial_names_its_candidate(self, session, journalled):
        report = journalled(IMPROVES)
        assert rows(session, trials, run_id="h1")[0]["candidate_fingerprint"] == (
            report.best
        )

    def test_an_abandoned_trial_names_nothing(self, session, journalled):
        """It produced no candidate, so there is nothing to point at."""
        journalled(*[NONSENSE] * 4)
        assert rows(session, trials, run_id="h1")[0]["candidate_fingerprint"] is None


class TestAPoisonCandidate:
    """A candidate that keeps crashing must not come back alive after a
    restart. That is the whole reason the crash count is a column."""

    def test_a_crash_is_counted_against_the_candidate(self, session, journalled):
        journalled(CRASHES)
        crashed = next(
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        )
        assert crashed["crashes"] == 1

    def test_it_stays_alive_while_it_is_under_the_limit(self, session, journalled):
        journalled(CRASHES)
        crashed = next(
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        )
        assert crashed["status"] == CandidateState.ALIVE

    def test_enough_crashes_quarantine_it(self, session, journalled):
        journalled(*[CRASHES] * 3, budget=3)
        crashed = next(
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        )
        assert crashed["status"] == CandidateState.QUARANTINED

    def test_a_scored_candidate_is_never_counted_against(self, session, journalled):
        journalled(IMPROVES)
        best = next(
            row for row in rows(session, candidates, run_id="h1") if row["parent_id"]
        )
        assert best["crashes"] == 0


class TestARunSaysWhoAskedForItAndWhy:
    """One database shared by a group is unreadable without these. Both are
    written once, at the start, and never updated."""

    def test_the_owner_is_written(self, session, journalled):
        journalled(IMPROVES, owner="her@lab.edu")
        assert rows(session, runs, id="h1")[0]["owner"] == "her@lab.edu"

    def test_the_experiment_is_written(self, session, journalled):
        journalled(IMPROVES, label="cache-eviction")
        assert rows(session, runs, id="h1")[0]["experiment"] == "cache-eviction"

    def test_neither_is_required(self, session, journalled):
        """A solo run on a laptop has no group to be legible to."""
        journalled(IMPROVES)
        row = rows(session, runs, id="h1")[0]
        assert (row["owner"], row["experiment"]) == (None, None)

    def test_they_survive_the_run_finishing(self, session, journalled):
        """RunFinished updates the row. An update that named every column
        would blank the two nothing thought to carry forward."""
        journalled(IMPROVES, owner="her@lab.edu", label="cache-eviction")
        row = rows(session, runs, id="h1")[0]
        assert row["status"] == RunState.FINISHED
        assert (row["owner"], row["experiment"]) == ("her@lab.edu", "cache-eviction")
