from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadence.control.region import BEGIN, END
from cadence.core.types import NonBlank
from cadence.errors import ManifestError
from cadence.parsing.metrics import Goal

__all__ = ["API_VERSIONS", "Manifest", "Plugin", "load"]

API_VERSIONS = ("cadence/v1alpha1",)
FILENAME = ".cadence"

DEFAULT_METHOD = "evolution"
DEFAULT_MODEL = "scripted"

DEFAULT_GUIDANCE = "IMPROVE.md"
DEFAULT_RUN = "python {program}"


class Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Plugin(Strict):
    name: NonBlank
    options: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _from_single_key(cls, value: Any) -> Any:
        if not isinstance(value, Mapping) or set(value) <= {"name", "options"}:
            return value
        if len(value) != 1:
            raise ValueError(f"name exactly one, got {', '.join(sorted(value))}")
        [(name, options)] = value.items()
        return {"name": name, "options": options or {}}


class Markers(Strict):
    begin: NonBlank = BEGIN
    end: NonBlank = END

    @model_validator(mode="after")
    def _distinct(self) -> "Markers":
        if self.begin == self.end:
            raise ValueError("begin and end markers must differ")
        return self


class Budget(Strict):
    trials: int = Field(default=20, gt=0)


class Sandbox(Strict):
    seconds: float = Field(default=10.0, gt=0)
    memory_mb: int = Field(default=256, gt=0)
    seeds: tuple[int, ...] = (0, 1, 2)


class Manifest(Strict):
    api_version: NonBlank = Field(alias="apiVersion")
    program: NonBlank
    metrics: Mapping[NonBlank, Goal] = Field(min_length=1)
    run: NonBlank = DEFAULT_RUN
    guidance: NonBlank = DEFAULT_GUIDANCE
    task: NonBlank | None = None
    method: Plugin = Plugin(name=DEFAULT_METHOD)
    model: Plugin = Plugin(name=DEFAULT_MODEL)
    objective: Plugin | None = None
    markers: Markers = Markers()
    budget: Budget = Budget()
    sandbox: Sandbox = Sandbox()

    @model_validator(mode="after")
    def _known_api_version(self) -> "Manifest":
        if self.api_version not in API_VERSIONS:
            known = ", ".join(API_VERSIONS)
            raise ValueError(
                f"apiVersion {self.api_version!r} is not supported by this"
                f" version of cadence; known versions: {known}"
            )
        return self

    @property
    def command(self) -> str:
        return self.run.format(program=self.program)

    @property
    def _objective(self) -> str:
        if self.objective is None:
            named = " and ".join(f"{v} {k}" for k, v in self.metrics.items())
            return f"{named}"
        return f"{self.objective.name} {dict(self.objective.options)}"

    @property
    def _named_metrics(self) -> str:
        return ", ".join(f"{name} ({goal})" for name, goal in self.metrics.items())

    @property
    def plan(self) -> str:
        return "\n".join(
            [
                f"  program    {self.program}",
                f"  run        {self.command}",
                f"  metrics    {self._named_metrics}",
                f"  guidance   {self.guidance}",
                f"  markers    {self.markers.begin} .. {self.markers.end}",
                f"  method     {_plugin(self.method)}",
                f"  objective  {self._objective}",
                f"  model      {_plugin(self.model)}",
                f"  budget     {self.budget.trials} trials",
                f"  sandbox    {self.sandbox.seconds}s, {self.sandbox.memory_mb}MB,"
                f" seeds {list(self.sandbox.seeds)}",
            ]
        )


def _plugin(plugin: Plugin) -> str:
    return f"{plugin.name} {dict(plugin.options) or ''}".rstrip()


def load(path: str | Path = FILENAME) -> Manifest:
    path = Path(path)
    if path.is_dir():
        path = path / FILENAME
    if not path.exists():
        raise ManifestError(
            f"no {FILENAME} at {path}; that file is where a cadence project starts"
        )
    try:
        document = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ManifestError(f"{path} is not valid YAML: {error}") from error
    if document is None:
        document = {}
    if not isinstance(document, Mapping):
        raise ManifestError(
            f"{path} should contain a mapping, not {type(document).__name__}"
        )
    try:
        return Manifest.model_validate(document)
    except Exception as error:
        raise ManifestError(
            f"{path} is not a valid manifest:\n{_explain(error)}"
        ) from error


def _explain(error: Exception) -> str:
    errors = getattr(error, "errors", None)
    if errors is None:
        return f"  {error}"
    return "\n".join(f"  {_where(item['loc'])}: {item['msg']}" for item in errors())


def _where(location: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in location) or "(root)"
