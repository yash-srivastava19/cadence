import threading
import time

import pytest

from cadence.control.locking import LocalLocks
from cadence.core.ports import Locks
from cadence.errors import LockUnavailable


class TestALockInOneProcess:
    def test_it_satisfies_the_port(self):
        assert isinstance(LocalLocks(), Locks)

    def test_the_body_runs_holding_the_lock(self):
        locks = LocalLocks()
        with locks.with_lock("runs/h1"):
            assert True

    def test_the_lock_is_free_again_afterwards(self):
        locks = LocalLocks()
        with locks.with_lock("runs/h1"):
            pass
        with locks.with_lock("runs/h1"):
            pass

    def test_it_is_released_even_when_the_body_raises(self):
        locks = LocalLocks()
        with pytest.raises(ValueError, match="failed"), locks.with_lock("runs/h1"):
            raise ValueError("the write failed")
        with locks.with_lock("runs/h1"):
            pass

    def test_two_keys_do_not_wait_on_each_other(self):
        locks = LocalLocks()
        with locks.with_lock("runs/h1"), locks.with_lock("runs/h2"):
            assert True


class TestWhenSomeoneElseHasIt:
    def test_a_second_holder_is_refused_rather_than_left_waiting(self):
        locks = LocalLocks(wait=0.05)
        failed = []

        def contend():
            try:
                with locks.with_lock("runs/h1"):
                    pass
            except LockUnavailable as error:
                failed.append(error)

        with locks.with_lock("runs/h1"):
            other = threading.Thread(target=contend)
            other.start()
            other.join()

        assert len(failed) == 1
        assert "another thread" in str(failed[0])

    def test_it_gives_up_after_the_wait_rather_than_hanging(self):
        locks = LocalLocks(wait=0.05)
        started = 0.0
        with locks.with_lock("runs/h1"):
            started = time.monotonic()
            other = threading.Thread(target=_take, args=(locks,))
            other.start()
            other.join()
        assert time.monotonic() - started < 2.0

    def test_the_wait_can_be_set_per_call(self):
        locks = LocalLocks(wait=10.0)
        held = threading.Lock()
        held.acquire()

        def contend():
            with pytest.raises(LockUnavailable), locks.with_lock("runs/h1", wait=0.01):
                pass

        with locks.with_lock("runs/h1"):
            other = threading.Thread(target=contend)
            other.start()
            other.join()


def _take(locks):
    """Contends for a held lock and is expected to be refused."""
    with pytest.raises(LockUnavailable), locks.with_lock("runs/h1"):
        pass
