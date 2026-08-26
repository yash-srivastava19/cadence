__all__ = [
    "CadenceError",
    "SetupError",
    "ModelError",
    "RetryableModelError",
    "TerminalModelError",
    "PatchError",
    "NoCandidates",
]


class CadenceError(Exception): ...


class SetupError(CadenceError):
    """The user's project is wrong. Retrying cannot help, so the run stops."""


class ModelError(CadenceError): ...


class RetryableModelError(ModelError): ...


class TerminalModelError(ModelError): ...


class PatchError(CadenceError): ...


class NoCandidates(CadenceError): ...
