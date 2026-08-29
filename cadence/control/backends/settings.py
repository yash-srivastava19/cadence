import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cadence.errors import MissingKey, UnknownProvider

__all__ = ["ANY_MODEL", "LOCAL", "Price", "Settings", "known", "settings_for"]

FILE = Path(__file__).with_name("providers.yml")
LOCAL = "providers.local.yml"

#: A price that applies whatever model was named. What a local runtime has:
#: nothing it serves is billed, so naming each model would be a list to keep.
ANY_MODEL = "*"

#: Prices are quoted per million tokens because that is how every provider
#: publishes them, so a user copying a number off a pricing page copies it
#: unchanged. Dividing happens once, here, rather than in every row.
PER = 1_000_000


class Price(BaseModel):
    """What a model costs, in USD per million tokens, as the user declared it.

    Cadence ships one of these and only one -- zero, for a local runtime.
    Every other price is a fact about someone else's catalogue that was true
    on the day it was written, so it lives in the user's own
    providers.local.yml where they can see how old it is.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    input: float = Field(ge=0, alias="in")
    output: float = Field(ge=0, alias="out")

    def of(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.input + tokens_out * self.output) / PER


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    base_url: str
    key_from: tuple[str, ...] = ()
    model: str
    temperature: float = Field(ge=0)
    timeout: float = Field(gt=0)
    attempts: int = Field(ge=1)
    backoff: float = Field(ge=0)
    key: str | None = None
    prices: Mapping[str, Price] = {}
    #: The header this provider dedupes on, if it has one. Absent means it
    #: does not, and a retried call is a second charge.
    idempotency_header: str | None = None

    @property
    def url(self) -> str:
        return self.base_url.rstrip("/")

    @property
    def needs_a_key(self) -> bool:
        return bool(self.key_from)

    def price_of(self, model: str) -> Price | None:
        """What this provider charges for that model, if anyone has said.

        None is a real answer and not a failure: no price declared means a run
        reports the tokens it spent and stays quiet about money, which is the
        honest thing to do with a number nobody gave us.
        """
        return self.prices.get(model) or self.prices.get(ANY_MODEL)

    def headers(self, key: str | None = None) -> dict[str, str]:
        """What this provider needs on the wire to accept a request.

        The key names this call, so a retry after a timeout is recognised as
        the same one. A timeout is exactly when the provider may have answered
        a request we never saw, and a blind second attempt is a second charge.
        """
        sending = {}
        if self.needs_a_key:
            sending["Authorization"] = f"Bearer {self.demand_key()}"
        if key and self.idempotency_header:
            sending[self.idempotency_header] = key
        return sending

    def demand_key(self) -> str:
        if self.key:
            return self.key
        raise MissingKey(
            f"{self.name} needs an API key. Set {' or '.join(self.key_from)}"
            " in your environment - cadence never reads one from a file,"
            " so a secret manager works without configuring anything."
        )


def _document(root: Path | None = None) -> Mapping[str, Any]:
    shipped = yaml.safe_load(FILE.read_text())
    local = (root or Path.cwd()) / LOCAL
    if not local.exists():
        return shipped
    return _merged(shipped, yaml.safe_load(local.read_text()) or {})


def _merged(under: Mapping[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(under)
    for key, value in over.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _merged(out[key], value)
        else:
            out[key] = value
    return out


def known(root: Path | None = None) -> tuple[str, ...]:
    return tuple(sorted(_document(root)["providers"]))


def settings_for(name: str, root: Path | None = None, **overrides: Any) -> Settings:
    document = _document(root)
    if name not in document["providers"]:
        raise UnknownProvider(
            f"no provider named {name!r}; known: {', '.join(known(root))}"
        )
    declared = dict(document["providers"][name])
    base_from = declared.pop("base_url_from", None)
    key_from = declared.pop("key_from", None) or []
    if isinstance(key_from, str):
        key_from = [key_from]

    fields = {"name": name, **document["defaults"], **declared}
    fields["key_from"] = tuple(key_from)
    if base_from and os.environ.get(base_from):
        fields["base_url"] = os.environ[base_from]
    if key_from:
        fields["key"] = _first_set(key_from)
    fields.update({k: v for k, v in overrides.items() if v is not None})
    if not fields.get("model"):
        raise UnknownProvider(
            f"{name} has no default model; name one in .cadence:"
            f"  model: {{{name}: {{model: ...}}}}"
        )
    if "key" in declared:
        raise MissingKey(
            f"{LOCAL} sets a key for {name!r}; keys belong in the environment,"
            " never in a file beside the repo"
        )
    return Settings(**fields)


def _first_set(names: str | list[str]) -> str | None:
    for name in [names] if isinstance(names, str) else names:
        value = os.environ.get(name)
        if value:
            return value
    return None
