__all__ = [
    "CadenceError",
    "ModelError",
    "RetryableModelError",
    "TerminalModelError",
    "PatchError",
]


class CadenceError(Exception): ...


class ModelError(CadenceError): ...


class RetryableModelError(ModelError): ...


class TerminalModelError(ModelError): ...


class PatchError(CadenceError): ...
