"""What only a real lease can do.

The behaviour every lock shares is in tests/unit/test_locking.py, run against
both implementations. What is left here needs a lock that can expire while its
holder is still working, which a threading.Lock cannot.
"""

import os
import time

import pytest

URL = os.environ.get("REDIS_URL")

if not URL:
    pytest.skip("needs REDIS_URL; run 'docker compose up -d'", allow_module_level=True)

pytest.importorskip("redis", reason="run 'pip install -e .'")

from cadence.control.locking import redis_locks  # noqa: E402
from cadence.errors import LockLost, LockUnavailable  # noqa: E402

KEY = "runs/h1"
HELD = f"cadence:lock:{KEY}"


@pytest.fixture
def locks():
    service = redis_locks(URL, wait=0.2)
    service.client.flushdb()
    return service


class TestTheKeyIsReallyTaken:
    def test_the_key_exists_while_the_body_runs(self, locks):
        with locks.with_lock(KEY):
            assert locks.client.exists(HELD)

    def test_it_is_gone_afterwards(self, locks):
        with locks.with_lock(KEY):
            pass
        assert not locks.client.exists(HELD)

    def test_a_crashed_holder_does_not_keep_it_forever(self, locks):
        """The lease is what makes a lock survivable. Without it, a worker
        killed mid-section holds a key until a person notices."""
        locks.client.set(HELD, "someone-else", px=100)
        with locks.with_lock(KEY, wait=2.0):
            assert True


class TestWhenTheLeaseRunsOutFirst:
    def test_finishing_without_the_lock_is_an_error_not_a_shrug(self, locks):
        """Another worker may have been inside at the same time. A unique
        constraint decides whether that mattered; this is how the caller
        learns that it has to care."""
        with pytest.raises(LockLost, match="expired"), locks.with_lock(KEY, ttl=0.1):
            time.sleep(0.3)

    def test_we_do_not_release_a_lock_somebody_else_now_holds(self, locks):
        """Why redis-py's Lock rather than SET and DEL: the release is a
        compare-and-delete against our own token."""
        other = redis_locks(URL, wait=1.0)
        with (  # noqa: PT012
            pytest.raises(LockLost),
            locks.with_lock(KEY, ttl=0.1),
        ):
            time.sleep(0.2)
            with other.with_lock(KEY):
                assert other.client.exists(HELD)

    def test_the_body_failing_is_what_the_caller_sees(self, locks):
        """Not a release problem discovered on the way out, even though the
        lease expired here too."""
        with (  # noqa: PT012
            pytest.raises(ValueError, match="failed"),
            locks.with_lock(KEY, ttl=0.1),
        ):
            time.sleep(0.2)
            raise ValueError("the write failed")


class TestWhenRedisIsNotThere:
    def test_it_says_it_could_not_reach_the_lock(self):
        unreachable = redis_locks("redis://127.0.0.1:1/0", wait=0.1)
        with (
            pytest.raises(LockUnavailable, match="could not reach"),
            unreachable.with_lock(KEY),
        ):
            pass

    def test_it_does_not_quietly_carry_on_without_one(self):
        unreachable = redis_locks("redis://127.0.0.1:1/0", wait=0.1)
        ran = []
        with pytest.raises(LockUnavailable), unreachable.with_lock(KEY):
            ran.append(True)
        assert ran == []
