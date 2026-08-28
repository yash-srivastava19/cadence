"""The provider is the problem.

The split that matters is whether asking again could work. A 429 is worth a
backoff; a 401 is worth nothing at all, and spending three attempts on it just
delays the message the user needs to read.
"""

from cadence.errors.base import CadenceError

__all__ = [
    "ModelError",
    "PromptChanged",
    "RetryableModelError",
    "TerminalModelError",
]


class ModelError(CadenceError):
    """Something went wrong reaching or reading a model."""


class RetryableModelError(ModelError):
    """A timeout, a 429, a 5xx. Back off and ask again."""


class TerminalModelError(ModelError):
    """A 401, a 404, a refusal, a body we cannot read. Asking again is waste."""


class PromptChanged(ModelError):
    """A replayed call was recorded against a different prompt.

    The run is not reproducing what it did before, so its recorded answers are
    answers to questions we are no longer asking.
    """
