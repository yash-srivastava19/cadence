__all__ = [
    "CadenceError",
    "ModelError",
    "RetryableModelError",
    "TerminalModelError",
    "PatchError",
    "NoCandidates",
]


class CadenceError(Exception): ...


class ModelError(CadenceError): ...


class RetryableModelError(ModelError): ...


class TerminalModelError(ModelError): ...


class PatchError(CadenceError): ...


class NoCandidates(CadenceError): ...
