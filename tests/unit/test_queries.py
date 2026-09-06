from datetime import UTC, datetime, timedelta

from cadence.control.queries import _stalled
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
