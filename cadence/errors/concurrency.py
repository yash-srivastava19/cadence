"""Two workers wanted the same thing.

Nothing here means the data is wrong. It means someone else is doing this
work, or that we can no longer prove we were the only one doing it.
"""

from cadence.errors.base import CadenceError

__all__ = ["LockError", "LockLost", "LockUnavailable"]


class LockError(CadenceError):
    """Something went wrong taking or holding a lock."""


class LockUnavailable(LockError):
    """Someone else holds it, or the lock service could not be reached.

    Not a failure of the work: the caller should wait and try again, or leave
    this piece of work to whoever holds the lock.
    """


class LockLost(LockError):
    """We held it, finished, and no longer held it by the end.

    The lease expired mid-section, so another worker may have been inside at
    the same time. Loud on purpose: the write may have raced, and whether it
    did is a question only the database's constraints can answer.
    """
