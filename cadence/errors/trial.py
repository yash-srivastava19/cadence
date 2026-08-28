"""This one candidate is no good. The run carries on.

Nothing here says the project is wrong, so none of it stops a run: a patch
that will not apply costs a trial, and a program that printed no metric scores
as invalid and becomes something to tell the model about.
"""

from cadence.errors.base import CadenceError

__all__ = [
    "EmptyReply",
    "MetricNotReported",
    "NoCandidates",
    "PatchError",
    "UnusableReply",
]


class UnusableReply(CadenceError):
    """The model answered, and nothing can be built from what it said.

    Worth asking again for: it costs a model call, not a trial, until the
    retry budget is gone.
    """


class PatchError(UnusableReply):
    """The reply could not be turned into a diff, or the diff would not apply."""


class EmptyReply(UnusableReply):
    """The provider returned a well-formed reply carrying no completion.

    A content filter, or a truncation. Distinct from a body cadence cannot
    read at all, which is terminal: this one is usually about this prompt.
    """


class MetricNotReported(CadenceError):
    """The program ran and never printed a metric that was asked for.

    Deliberately not a SetupError, though `cadence check` treats it as one:
    the baseline failing this way is the project's fault, a candidate failing
    it is the candidate's, and the same class serves both because the caller
    knows which it is holding.
    """


class NoCandidates(CadenceError):
    """The search has nothing left alive to improve."""
