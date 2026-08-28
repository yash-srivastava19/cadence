"""Taking a lock, so that two workers do not do one piece of work.

Two implementations behind one port:

- ``RedisLocks`` for more than one process, wrapping redis-py's Lock. That
  class already holds a random token per acquisition and releases with a Lua
  compare-and-delete, which is the part worth not writing again: a plain
  ``DEL`` will happily delete a lock that expired and was taken by somebody
  else in the meantime.
- ``LocalLocks`` for one process, and for tests. It is not a substitute for
  the other one across a network, which is why nothing falls back to it
  silently -- a process-local lock standing in for a distributed one is a
  race that only appears in production.

What a lock here is for: not doing the same work twice, and not contending.
It is not what makes a double write impossible. A lease can expire while its
holder is still inside the section, so the database's unique constraints stay
the actual guarantee, and LockLost is how a caller finds out that it has to
rely on them.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from redis import Redis
from redis import exceptions as redis_errors

from cadence.errors import LockLost, LockUnavailable

__all__ = ["DEFAULT_TTL", "DEFAULT_WAIT", "LocalLocks", "RedisLocks", "redis_locks"]

#: How long a lock lives if its holder never releases it -- a crashed worker
#: must not lock a key forever. Long enough for a database write and short
#: enough that a dead worker is not waited on.
DEFAULT_TTL = 30.0

#: How long to wait to take a lock before giving up and saying so.
DEFAULT_WAIT = 5.0

PREFIX = "cadence:lock:"


class RedisLocks:
    def __init__(
        self,
        client: Redis,
        *,
        prefix: str = PREFIX,
        ttl: float = DEFAULT_TTL,
        wait: float = DEFAULT_WAIT,
        poll: float = 0.05,
    ) -> None:
        self.client = client
        self.prefix = prefix
        self.ttl = ttl
        self.wait = wait
        self.poll = poll

    @contextmanager
    def with_lock(
        self, key: str, *, ttl: float | None = None, wait: float | None = None
    ) -> Iterator[None]:
        """Hold `key` for the body, or raise rather than run it unguarded."""
        lock = self.client.lock(
            f"{self.prefix}{key}",
            timeout=ttl or self.ttl,
            blocking=True,
            blocking_timeout=wait if wait is not None else self.wait,
            sleep=self.poll,
        )
        try:
            taken = lock.acquire()
        except redis_errors.RedisError as error:
            # Unreachable, refusing us, or timing out. From the caller's side
            # this is the same as somebody else holding it: not ours to enter.
            raise LockUnavailable(f"could not reach the lock for {key!r}") from error
        if not taken:
            raise LockUnavailable(
                f"{key!r} is held by another worker"
                f" (waited {wait if wait is not None else self.wait:g}s)"
            )
        try:
            yield
        except BaseException:
            # The body already failed. Releasing may fail too, and saying so
            # here would replace the failure the caller needs to see.
            self._release_quietly(lock)
            raise
        self._release(lock)

    def _release(self, lock) -> None:
        try:
            lock.release()
        except redis_errors.LockNotOwnedError as error:
            raise LockLost(
                "the lock expired before the work finished, so another worker"
                " may have been inside it at the same time"
            ) from error
        except redis_errors.RedisError as error:
            raise LockLost("could not release the lock") from error

    def _release_quietly(self, lock) -> None:
        with suppress(redis_errors.RedisError):
            lock.release()


class LocalLocks:
    """One process only. Good enough for a single-worker run and for tests."""

    def __init__(self, *, wait: float = DEFAULT_WAIT) -> None:
        self.wait = wait
        self._keys: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    @contextmanager
    def with_lock(
        self, key: str, *, ttl: float | None = None, wait: float | None = None
    ) -> Iterator[None]:
        # ttl is accepted and ignored: a lock held inside this process cannot
        # outlive the process, so there is nothing for a lease to protect us
        # from. The port keeps the argument so callers do not branch.
        lock = self._for(key)
        if not lock.acquire(timeout=wait if wait is not None else self.wait):
            raise LockUnavailable(f"{key!r} is held by another thread")
        try:
            yield
        finally:
            lock.release()

    def _for(self, key: str) -> threading.Lock:
        with self._guard:
            return self._keys.setdefault(key, threading.Lock())


def redis_locks(url: str, **options: float | str) -> RedisLocks:
    """Build a lock service against `url`.

    No fallback if it cannot be reached. A silent downgrade to LocalLocks
    would turn a broken deployment into a race nobody can reproduce.
    """
    return RedisLocks(Redis.from_url(url), **options)  # type: ignore[arg-type]
