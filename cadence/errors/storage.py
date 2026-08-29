"""The database is the problem, not the project and not the model.

Separate from setup.py because the fix is somewhere else: a manifest error is
answered by editing a file in the repo, and everything here is answered by
starting a container or running a migration. Same policy -- stop the run and
say so -- but the sentence the user needs to read is different.

These are deliberately not SetupError: Experiment turns a SetupError into a
failed Report, which means writing a RunFinished, which means another write to
the database that just failed. A storage failure travels past the loop to the
command, which has no session to lose.
"""

from cadence.errors.base import CadenceError

__all__ = ["SchemaOutOfDate", "StorageError"]


class StorageError(CadenceError):
    """Cadence could not reach or use the database it was pointed at."""


class SchemaOutOfDate(StorageError):
    """The database exists and its schema is not the one this code writes.

    Loud on purpose, and checked before the first trial rather than at the
    first write: a run that discovers this at trial 300 has spent three
    hundred trials' worth of model calls to learn something one query at
    startup could have told it.
    """
