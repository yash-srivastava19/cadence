"""What every lock must do, whichever one it is.

The shared behaviour is written once and run against both implementations --
the test id says which one failed. Behaviour only a real lease can have
(expiring mid-section, releasing somebody else's lock) lives in
tests/integration/test_locking.py, because only redis has a lease.
"""

import os
import threading
import time

import pytest

from cadence.control.locking import LocalLocks, redis_locks
from cadence.core.ports import Locks
from cadence.errors import LockUnavailable

KEY = "runs/h1"
REDIS_URL = os.environ.get("REDIS_URL")


@pytest.fixture(params=["local", "redis"])
def locks(request):
    """Both implementations of Locks. redis is skipped when there is none."""
    if request.param == "local":
        return LocalLocks(wait=0.05)
    if not REDIS_URL:
        pytest.skip("needs REDIS_URL; run 'docker compose up -d'")
    service = redis_locks(REDIS_URL, wait=0.05)
    service.client.flushdb()
    return service


class TestAnyLock:
    def test_it_satisfies_the_port(self, locks):
        assert isinstance(locks, Locks)

    def test_the_body_runs(self, locks):
        ran = []
        with locks.with_lock(KEY):
            ran.append(True)
        assert ran == [True]

    def test_the_key_is_free_again_afterwards(self, locks):
        with locks.with_lock(KEY):
            pass
        with locks.with_lock(KEY):
            pass

    def test_it_is_freed_even_when_the_body_raises(self, locks):
        with pytest.raises(ValueError, match="failed"), locks.with_lock(KEY):
            raise ValueError("the write failed")
        with locks.with_lock(KEY):
            pass

    def test_two_keys_do_not_wait_on_each_other(self, locks):
        with locks.with_lock("runs/h1"), locks.with_lock("runs/h2"):
            pass

    def test_a_second_holder_is_refused_rather_than_left_waiting(self, locks):
        refused = _contend(locks, KEY)
        with locks.with_lock(KEY):
            refused.start()
            refused.join(timeout=5)
        assert not refused.is_alive()
        assert refused.refused, "the second holder was let in"

    def test_it_gives_up_within_the_wait_it_was_given(self, locks):
        started = 0.0
        with locks.with_lock(KEY):
            started = time.monotonic()
            other = _contend(locks, KEY)
            other.start()
            other.join(timeout=5)
        assert time.monotonic() - started < 2.0


def _contend(locks, key):
    """A second holder, which is expected to be turned away."""

    class Contender(threading.Thread):
        refused = False

        def run(self):
            try:
                with locks.with_lock(key, wait=0.05):
                    pass
            except LockUnavailable:
                self.refused = True

    return Contender()
