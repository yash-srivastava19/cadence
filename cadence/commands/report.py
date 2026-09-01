"""How a command talks.

Findings go to stdout in two columns: what was checked, and what was found.
Anything that is not a finding goes to stderr, so `cadence check > findings`
keeps only the findings.

Supports both human-friendly and machine-readable (JSON) output modes.
All commands can use @json_capable decorator for automatic JSON support.
"""

import contextvars
import functools
import json
from collections.abc import Callable
from typing import NoReturn, TypeVar

import typer

LABEL = 12

_output_mode: contextvars.ContextVar[str] = contextvars.ContextVar(
    "output_mode", default="human"
)
_findings: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "findings", default=None
)

F = TypeVar("F", bound=Callable)


def set_output_mode(mode: str) -> None:
    """Set output mode for this context (human or json)."""
    _output_mode.set(mode)
    if mode == "json":
        _findings.set({"findings": [], "warnings": []})


def get_output_mode() -> str:
    """Get current output mode."""
    return _output_mode.get()


def found(label: str, detail: str) -> None:
    """A check that passed, and what it saw."""
    if _output_mode.get() == "json":
        findings = _findings.get()
        if findings:
            findings["findings"].append({"label": label, "detail": detail})
            _findings.set(findings)
    else:
        typer.echo(f"  {label:<{LABEL}}{detail}")


def absent(label: str, detail: str) -> None:
    """Something optional that is not there. Not a failure."""
    if _output_mode.get() == "json":
        findings = _findings.get()
        if findings:
            findings["warnings"].append({"label": label, "detail": detail})
            _findings.set(findings)
    else:
        typer.echo(f"  {label:<{LABEL}}{detail}")


def note(line: str) -> None:
    """Note goes to stderr, unless in JSON mode (then it's silent)."""
    if _output_mode.get() == "human":
        typer.echo(line, err=True)


def die(message: str, fix: str | None = None) -> NoReturn:
    """Exit with error, formatted for output mode."""
    if _output_mode.get() == "json":
        error = {"message": message}
        if fix:
            error["fix"] = fix
        typer.echo(json.dumps({"error": error}, indent=2))
    else:
        typer.echo(f"\n{message}", err=True)
        if fix:
            typer.echo(f"\n{fix}", err=True)
    raise typer.Exit(1)


def output_findings() -> None:
    """Output collected findings if in JSON mode."""
    if _output_mode.get() == "json":
        findings = _findings.get()
        if findings:
            typer.echo(json.dumps(findings, indent=2))


def json_capable(func: F) -> F:
    """Decorator to add --json flag to any command.

    Automatically handles JSON output mode for the decorated function.
    The function receives a `json_output: bool` parameter.
    """

    @functools.wraps(func)
    def wrapper(*args, json_output: bool = False, **kwargs):
        if json_output:
            set_output_mode("json")
        try:
            return func(*args, **kwargs)
        finally:
            if json_output:
                output_findings()
                _output_mode.set("human")
                _findings.set(None)

    # Add the json_output parameter to the signature
    wrapper.__doc__ = func.__doc__ or ""
    return wrapper  # type: ignore[return-value]
