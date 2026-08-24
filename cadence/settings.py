import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cadence.exceptions import CadenceError

__all__ = [
    "Settings",
    "UnknownProvider",
    "MissingKey",
    "known",
    "settings_for",
    "LOCAL",
]

FILE = Path(__file__).with_name("providers.yml")
LOCAL = "providers.local.yml"


class UnknownProvider(CadenceError):
    pass


class MissingKey(CadenceError):
    pass


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

    def demand_key(self) -> str:
        if self.key:
            return self.key
        raise MissingKey(
            f"{self.name} needs an API key; set {' or '.join(self.key_from)}"
            f" in .env, or key: in {LOCAL}"
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
    return Settings(**fields)


def _first_set(names: str | list[str]) -> str | None:
    for name in [names] if isinstance(names, str) else names:
        value = os.environ.get(name)
        if value:
            return value
    return None
