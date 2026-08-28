"""The field types every DTO is built from.

Declared once here rather than re-derived in each module: NonBlank alone was
spelled out in seven files, and a constraint that is copied is a constraint
that drifts.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, TypeVar

from pydantic import AfterValidator, Field, PlainSerializer, StringConstraints

__all__ = ["Frozen", "Metric", "Metrics", "NonBlank"]

K = TypeVar("K")
V = TypeVar("V")


def _freeze(value: Mapping) -> Mapping:
    return MappingProxyType(dict(value))


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

#: A measurement. Never NaN or infinite -- those compare in ways an objective
#: cannot rank, so they are refused where they enter rather than guarded for
#: at every comparison.
Metric = Annotated[float, Field(allow_inf_nan=False)]

Metrics = Mapping[str, float]

#: A mapping that cannot be edited after validation, and still serialises as
#: a plain dict.
Frozen = Annotated[Mapping[K, V], AfterValidator(_freeze), PlainSerializer(dict)]
