"""The project is wrong. Retrying cannot help, so the run stops.

Asking a model again for a file whose markers are broken spends the whole
budget producing the same failure, which is why these are separated from the
errors in trial.py by policy rather than by subject.
"""

from cadence.errors.base import CadenceError

__all__ = [
    "ManifestError",
    "MarkerError",
    "MissingKey",
    "MissingMetric",
    "SetupError",
    "UnknownPlugin",
    "UnknownProvider",
]


class SetupError(CadenceError):
    """The user's project is wrong. Retrying cannot help, so the run stops."""


class ManifestError(SetupError):
    """.cadence is missing, unreadable, or says something cadence cannot honour."""


class MarkerError(SetupError):
    """The program does not have exactly one marked region."""


class MissingMetric(SetupError):
    """The objective ranks by a metric the verdict does not carry."""


class UnknownPlugin(SetupError):
    """No method, objective or backend goes by that name, or by those options."""


class UnknownProvider(SetupError):
    """No row in providers.yml goes by that name."""


class MissingKey(SetupError):
    """A provider needs an API key and the environment does not have one."""
