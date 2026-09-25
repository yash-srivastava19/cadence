from datetime import UTC, datetime, timedelta

from cadence.control.queries import _declared, _stalled
from cadence.lifecycle.states import RunState


class TestARunThatStoppedWithoutSayingSo:
    """RunFinished is published by the loop, so a process that is killed --
    Ctrl-C, an OOM, a laptop closing -- leaves RUNNING behind and keeps it.
    The one command for "what is happening" then reports things that are not
    happening."""

    def _ago(self, **kwargs):
        return datetime.now(UTC) - timedelta(**kwargs)

    def test_a_quiet_running_run_is_stalled(self):
        assert _stalled(RunState.RUNNING, self._ago(hours=9))

    def test_a_run_that_just_wrote_is_not(self):
        assert not _stalled(RunState.RUNNING, self._ago(seconds=5))

    def test_a_slow_model_call_is_not_a_stall(self):
        """ModelRequested is journalled before the call, not after, so a run
        waiting on a slow provider has still touched the tape recently."""
        assert not _stalled(RunState.RUNNING, self._ago(minutes=4))

    def test_a_finished_run_is_never_stalled(self):
        assert not _stalled(RunState.FINISHED, self._ago(days=30))

    def test_a_run_that_wrote_nothing_at_all_is_not_guessed_about(self):
        assert not _stalled(RunState.RUNNING, None)

    def test_a_naive_timestamp_is_read_as_utc(self):
        """Postgres hands these back tz-aware; older rows may not, and
        subtracting a naive one raises rather than answering."""
        naive = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=9)
        assert _stalled(RunState.RUNNING, naive)


class TestWhatTheManifestDeclares:
    """Which way a metric improves, read once here so the terminal and the
    browser cannot disagree about whether 8.26 is good."""

    MANIFEST = (
        "api_version: cadence/v1alpha2\n"
        "program: pack.py\n"
        "metrics:\n"
        "  sum_radii: maximize\n"
        "  excess_train: minimize\n"
        "budget:\n"
        "  trials: 20\n"
        "  usd: 2.0\n"
    )

    def test_it_reads_the_direction_of_every_metric(self):
        directions, _ = _declared(self.MANIFEST)
        assert directions == {"sum_radii": "maximize", "excess_train": "minimize"}

    def test_it_reads_the_trial_budget(self):
        assert _declared(self.MANIFEST)[1] == 20

    def test_a_manifest_that_will_not_parse_is_not_an_error(self):
        """The run still happened; a page renders without the direction
        rather than failing over a manifest nobody can read."""
        assert _declared("{[ oh no") == ({}, None)

    def test_a_manifest_that_is_not_a_mapping_is_not_an_error(self):
        assert _declared("- one\n- two\n") == ({}, None)

    def test_nothing_recorded_is_nothing_declared(self):
        assert _declared(None) == ({}, None)

    def test_a_budget_that_is_not_a_number_is_left_undeclared(self):
        assert _declared("budget:\n  trials: lots\n")[1] is None
