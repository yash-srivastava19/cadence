import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cadence.errors import MissingKey, UnknownProvider

__all__ = ["LOCAL", "Settings", "known", "settings_for"]

FILE = Path(__file__).with_name("providers.yml")
LOCAL = "providers.local.yml"


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

    @property
    def url(self) -> str:
        return self.base_url.rstrip("/")

    @property
    def needs_a_key(self) -> bool:
        return bool(self.key_from)

    def headers(self) -> dict[str, str]:
        """What this provider needs on the wire to accept a request."""
        if not self.needs_a_key:
            return {}
        return {"Authorization": f"Bearer {self.demand_key()}"}

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
