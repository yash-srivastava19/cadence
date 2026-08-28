"""Everything cadence raises, grouped by what the caller should do about it.

    setup.py   the project is wrong          -> stop the run, tell the user
    model.py   the provider is the problem   -> retry, or abandon the trial
    trial.py   this candidate is no good     -> score it and carry on

Grouped by policy rather than by subject, because the policy is what a caller
at the catch site is choosing between.
"""

from cadence.errors.base import CadenceError
from cadence.errors.model import (
    ModelError,
    PromptChanged,
    RetryableModelError,
    TerminalModelError,
)
from cadence.errors.setup import (
    ManifestError,
    MarkerError,
    MissingKey,
    MissingMetric,
    SetupError,
    UnknownPlugin,
    UnknownProvider,
)
from cadence.errors.trial import MetricNotReported, NoCandidates, PatchError

__all__ = [
    "CadenceError",
    "ManifestError",
    "MarkerError",
    "MetricNotReported",
    "MissingKey",
    "MissingMetric",
    "ModelError",
    "NoCandidates",
    "PatchError",
    "PromptChanged",
    "RetryableModelError",
    "SetupError",
    "TerminalModelError",
    "UnknownPlugin",
    "UnknownProvider",
]
