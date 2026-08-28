"""This one candidate is no good. The run carries on.

Nothing here says the project is wrong, so none of it stops a run: a patch
that will not apply costs a trial, and a program that printed no metric scores
as invalid and becomes something to tell the model about.
"""

from cadence.errors.base import CadenceError

__all__ = ["MetricNotReported", "NoCandidates", "PatchError"]


class PatchError(CadenceError):
    """The reply could not be turned into a diff, or the diff would not apply."""


class MetricNotReported(CadenceError):
    """The program ran and never printed a metric that was asked for.

    Deliberately not a SetupError, though `cadence check` treats it as one:
    the baseline failing this way is the project's fault, a candidate failing
    it is the candidate's, and the same class serves both because the caller
    knows which it is holding.
    """


class NoCandidates(CadenceError):
    """The search has nothing left alive to improve."""
