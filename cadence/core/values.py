"""The two bases every DTO in cadence inherits from.

Which one a class uses says whether its contents have been checked:

    Value   data cadence built itself, from parts it already trusts
    Parsed  data that arrived from outside -- a provider, the user's repo,
            the user's program -- and was validated at the boundary

Both are frozen. A DTO that can be edited after construction is a DTO whose
value depends on when you look at it.
"""

from pydantic import BaseModel, ConfigDict

__all__ = ["Parsed", "Value"]


class Value(BaseModel):
    """An internal record. Strict about types, and refuses unknown fields."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


class Parsed(BaseModel):
    """Data from outside, parsed at the edge.

    Not strict, because JSON gives an int where a float is meant, and extra
    fields are ignored rather than refused: a provider adding a field to its
    response is not an error, it is Tuesday.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")
