"""A run, one JSON line per step, in a file inside the project.

    <root>/cadence-runs/<env>/<run_id>.jsonl

The contract is thoughts/logging/contract.md: every line carries its run and
trial, a step has a start and an end, and content (code, replies, prompts)
appears only as a hash. Written directly and flushed per line, not queued: a
line costs microseconds against seconds of model call, and a queue would lose
the last lines on a crash -- the ones a post-mortem needs.
"""

import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import IO, Any

from cadence.core.identity import fingerprint
from cadence.core.verdict import Failed, Scored
from cadence.observe.channel import Fact
from cadence.observe.signals import (
    CandidateBuilt,
    Event,
    ModelCalled,
    ModelRequested,
    PatchRejected,
    ProposalReceived,
    RunFinished,
    RunResumed,
    RunStarted,
    SeedMeasured,
    TrialAbandoned,
    TrialMeasured,
    TrialRetried,
    TrialStarted,
)

__all__ = ["DIRECTORY", "KINDS", "RunLog", "environment"]

DIRECTORY = "cadence-runs"
ORDER = (
    "ts",
    "level",
    "run",
    "trial",
    "span",
    "phase",
    "status",
    "message",
    "id",
    "parent",
    "trace_id",
    "span_id",
    "parent_span_id",
    "duration_ms",
    "attrs",
)

#: What each field of each fact is, which decides how it is written. `content`
#: is replaced by its hash; `envelope` is already in the line's envelope.
KINDS: Mapping[type[Fact], Mapping[str, str]] = {
    RunStarted: {
        "run_id": "envelope",
        "at": "envelope",
        "method": "label",
        "manifest": "manifest",
        "seeds": "content",
        "budget": "number",
        "owner": "label",
        "experiment": "label",
    },
    RunResumed: {
        "run_id": "envelope",
        "at": "envelope",
        "trials": "number",
        "results": "number",
    },
    RunFinished: {
        "run_id": "envelope",
        "at": "envelope",
        "status": "label",
        "trials": "number",
        "best": "id",
        "reason": "text",
    },
    SeedMeasured: {
        "run_id": "envelope",
        "at": "envelope",
        "fingerprint": "id",
        "verdict": "verdict",
        "wall_ms": "number",
        "task_hash": "id",
        "seeds_hash": "id",
    },
    TrialStarted: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "seq": "number",
        "parent": "id",
    },
    ModelRequested: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "backend": "label",
        "key": "id",
        "prompt_digest": "id",
        "recipe": "content",
        "template": "label",
        "template_hash": "id",
    },
    ModelCalled: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "backend": "label",
        "key": "id",
        "response": "content",
        "model": "label",
        "replayed": "label",
        "tokens_in": "number",
        "tokens_out": "number",
        "latency_ms": "number",
        "cost_usd": "number",
    },
    ProposalReceived: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "files_changed": "number",
    },
    TrialRetried: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "reason": "text",
    },
    PatchRejected: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "reason": "text",
    },
    CandidateBuilt: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "fingerprint": "id",
        "code": "content",
        "parent": "id",
    },
    TrialMeasured: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "verdict": "verdict",
        "wall_ms": "number",
        "task_hash": "id",
        "seeds_hash": "id",
    },
    TrialAbandoned: {
        "run_id": "envelope",
        "at": "envelope",
        "trial_id": "envelope",
        "reason": "text",
    },
}


def _hex(kind: str, name: str, length: int) -> str:
    """An OTEL-shaped id derived from a cadence id: the same step always gets
    the same id, so a resumed run and a later OTEL export agree with this file."""
    return sha256(f"{kind}:{name}".encode()).hexdigest()[:length]


def environment() -> str:
    return os.environ.get("CADENCE_ENV") or "development"


def _version() -> str:
    try:
        return version("cadence")
    except PackageNotFoundError:
        return "unknown"


def _hashed(value: Any) -> str:
    if isinstance(value, str):
        return fingerprint(value)
    return fingerprint(json.dumps(value, sort_keys=True, default=str))


def _attrs(fact: Fact) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for field, kind in KINDS[type(fact)].items():
        value = getattr(fact, field)
        if kind == "envelope" or value is None:
            continue
        if kind == "content":
            attrs[f"{field}_hash"] = _hashed(value)
        elif kind == "verdict":
            attrs["outcome"] = str(value.outcome)
            attrs["candidate"] = value.fingerprint
            if isinstance(value, Scored):
                attrs["metrics"] = dict(value.metrics)
            else:
                attrs["reason"] = value.reason
        elif kind == "manifest":
            attrs["manifest_hash"] = value.hash
            attrs["api_version"] = value.api_version
            attrs["manifest"] = value.source
        elif isinstance(value, Mapping):
            attrs[field] = dict(value)
        else:
            if isinstance(value, float):
                attrs[field] = round(value, 3)
            elif isinstance(value, bool | int):
                attrs[field] = value
            else:
                attrs[field] = str(value)
    return attrs


def _scores(metrics: Mapping[str, float]) -> str:
    return ", ".join(f"{name}={value:g}" for name, value in metrics.items())


def _verdict(fact: SeedMeasured | TrialMeasured) -> tuple[str, str, str]:
    """status, level, and the words for it."""
    verdict = fact.verdict
    if isinstance(verdict, Failed):
        level = "error" if verdict.escalates else "info"
        last = verdict.reason.strip().splitlines()[-1] if verdict.reason.strip() else ""
        return f"failed:{verdict.outcome}", level, f"{verdict.outcome}: {last}"
    return "scored", "info", f"scored {_scores(verdict.metrics)}"


class RunLog:
    """A subscriber: every fact on the channel becomes one or more lines."""

    def __init__(self, root: Path, env: str | None = None) -> None:
        self.directory = root / DIRECTORY / (env or environment())
        self.env = env or environment()
        self._file: IO[str] | None = None
        self._path: Path | None = None
        self._started: dict[str, datetime] = {}
        self._call: dict[str, str] = {}
        self._calls: dict[str, int] = {}

    @property
    def path(self) -> Path | None:
        return self._path

    def __call__(self, fact: Fact) -> None:
        handler = HANDLERS.get(type(fact))
        if handler is None or not isinstance(fact, Event):
            return
        for record in handler(self, fact):
            self._write(fact, record)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def _open(self, run_id: str) -> IO[str]:
        if self._file is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            ignore = self.directory.parent / ".gitignore"
            if not ignore.exists():
                ignore.write_text("# Written by cadence: run logs stay local.\n*\n")
            self._path = self.directory / f"{run_id}.jsonl"
            # Line-buffered append: one write per line, flushed at the newline.
            self._file = open(  # noqa: SIM115 -- held for the run, closed in close()
                self._path, "a", encoding="utf-8", buffering=1
            )
        return self._file

    def _write(self, fact: Event, record: dict[str, Any]) -> None:
        run_id = fact.run_id
        trial = getattr(fact, "trial_id", None)
        envelope = {
            "ts": fact.at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.pop("level", "info"),
            "run": run_id,
            "trial": trial,
            **record,
        }
        envelope["trace_id"] = _hex("trace", trial or run_id, 32)
        envelope["span_id"] = _hex("span", envelope["id"], 16)
        if envelope.get("parent"):
            envelope["parent_span_id"] = _hex("span", envelope["parent"], 16)
        line = {key: envelope[key] for key in ORDER if envelope.get(key) is not None}
        self._open(run_id).write(
            json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n"
        )

    def _begin(self, step: str, at: datetime) -> None:
        self._started[step] = at

    def _took(self, step: str, at: datetime) -> float | None:
        began = self._started.pop(step, None)
        if began is None:
            return None
        return round((at - began).total_seconds() * 1000, 1)

    def _step(
        self,
        fact: Fact,
        span: str,
        phase: str,
        step: str,
        parent: str | None,
        message: str,
        status: str | None = None,
        level: str = "info",
        attrs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "span": span,
            "phase": phase,
            "status": status,
            "message": message,
            "level": level,
            "id": step,
            "parent": parent,
        }
        if phase == "start":
            self._begin(step, fact.at)
        elif phase == "end":
            record["duration_ms"] = self._took(step, fact.at)
        if attrs:
            record["attrs"] = attrs
        return record


Records = list[dict[str, Any]]


def _run_started(log: RunLog, fact: RunStarted) -> Records:
    attrs = _attrs(fact) | {"cadence_version": _version(), "env": log.env}
    return [
        log._step(
            fact,
            "run",
            "event",
            fact.run_id,
            None,
            f"run started: {fact.method}, {len(fact.seeds)} seed program(s)",
            status="started",
            attrs=attrs,
        )
    ]


def _run_resumed(log: RunLog, fact: RunResumed) -> Records:
    return [
        log._step(
            fact,
            "run",
            "event",
            fact.run_id,
            None,
            f"run resumed at trial {fact.trials}, {fact.results} results kept",
            status="resumed",
            attrs=_attrs(fact) | {"cadence_version": _version(), "env": log.env},
        )
    ]


def _run_finished(log: RunLog, fact: RunFinished) -> Records:
    level = "error" if fact.status == "failed" else "info"
    why = f": {fact.reason}" if fact.reason else ""
    return [
        log._step(
            fact,
            "run",
            "event",
            fact.run_id,
            None,
            f"run {fact.status} after {fact.trials} trials{why}",
            status=str(fact.status),
            level=level,
            attrs=_attrs(fact),
        )
    ]


def _baseline(log: RunLog, fact: SeedMeasured) -> Records:
    status, level, words = _verdict(fact)
    return [
        log._step(
            fact,
            "baseline",
            "event",
            f"{fact.run_id}/baseline/{fact.fingerprint}",
            fact.run_id,
            f"baseline {words}",
            status=status,
            level=level,
            attrs=_attrs(fact),
        )
    ]


def _trial_started(log: RunLog, fact: TrialStarted) -> Records:
    log._calls[fact.trial_id] = 0
    parent = fact.parent or "the seed"
    return [
        log._step(
            fact,
            "trial",
            "start",
            fact.trial_id,
            None,
            f"trial {fact.seq + 1} started from {parent}",
            attrs=_attrs(fact),
        )
    ]


def _model_requested(log: RunLog, fact: ModelRequested) -> Records:
    log._calls[fact.trial_id] = log._calls.get(fact.trial_id, 0) + 1
    step = f"{fact.trial_id}/call-{log._calls[fact.trial_id]}"
    log._call[fact.trial_id] = step
    return [
        log._step(
            fact,
            "model_call",
            "start",
            step,
            fact.trial_id,
            f"asking {fact.backend} (template {fact.template})",
            attrs=_attrs(fact),
        )
    ]


def _model_called(log: RunLog, fact: ModelCalled) -> Records:
    step = log._call.get(fact.trial_id, f"{fact.trial_id}/call")
    how = "replayed" if fact.replayed else f"{fact.latency_ms / 1000:.1f}s"
    return [
        log._step(
            fact,
            "model_call",
            "end",
            step,
            fact.trial_id,
            f"model replied: {fact.model},"
            f" {fact.tokens_in} in / {fact.tokens_out} out, {how}",
            status="ok",
            attrs=_attrs(fact),
        )
    ]


def _proposal(log: RunLog, fact: ProposalReceived) -> Records:
    call = log._call.get(fact.trial_id, f"{fact.trial_id}/call")
    patch = f"{fact.trial_id}/apply_patch"
    return [
        log._step(
            fact,
            "read_reply",
            "event",
            f"{call}/reply",
            call,
            f"reply read: {fact.files_changed} file(s) changed",
            status="ok",
            attrs=_attrs(fact),
        ),
        log._step(
            fact, "apply_patch", "start", patch, fact.trial_id, "applying the patch"
        ),
    ]


def _retried(log: RunLog, fact: TrialRetried) -> Records:
    call = log._call.get(fact.trial_id, f"{fact.trial_id}/call")
    return [
        log._step(
            fact,
            "read_reply",
            "event",
            f"{call}/reply",
            call,
            f"reply unusable, asking again: {fact.reason}",
            status="unusable",
            level="warn",
            attrs=_attrs(fact),
        )
    ]


def _abandoned(log: RunLog, fact: TrialAbandoned) -> Records:
    call = log._call.get(fact.trial_id, f"{fact.trial_id}/call")
    return [
        log._step(
            fact,
            "read_reply",
            "event",
            f"{call}/reply",
            call,
            f"reply unusable, no retries left: {fact.reason}",
            status="unusable",
            level="warn",
            attrs=_attrs(fact),
        ),
        log._step(
            fact,
            "trial",
            "end",
            fact.trial_id,
            None,
            "trial abandoned",
            status="abandoned",
            level="warn",
        ),
    ]


def _rejected(log: RunLog, fact: PatchRejected) -> Records:
    return [
        log._step(
            fact,
            "apply_patch",
            "end",
            f"{fact.trial_id}/apply_patch",
            fact.trial_id,
            f"patch rejected: {fact.reason}",
            status="rejected",
            level="warn",
            attrs=_attrs(fact),
        ),
        log._step(
            fact,
            "trial",
            "end",
            fact.trial_id,
            None,
            "trial rejected",
            status="rejected",
            level="warn",
        ),
    ]


def _built(log: RunLog, fact: CandidateBuilt) -> Records:
    return [
        log._step(
            fact,
            "apply_patch",
            "end",
            f"{fact.trial_id}/apply_patch",
            fact.trial_id,
            f"patch applied: candidate {fact.fingerprint}",
            status="ok",
            attrs=_attrs(fact),
        ),
        log._step(
            fact,
            "measure",
            "start",
            f"{fact.trial_id}/measure",
            fact.trial_id,
            f"measuring candidate {fact.fingerprint}",
        ),
    ]


def _measured(log: RunLog, fact: TrialMeasured) -> Records:
    status, level, words = _verdict(fact)
    return [
        log._step(
            fact,
            "measure",
            "end",
            f"{fact.trial_id}/measure",
            fact.trial_id,
            words,
            status=status,
            level=level,
            attrs=_attrs(fact),
        ),
        log._step(
            fact,
            "trial",
            "end",
            fact.trial_id,
            None,
            f"trial {words}",
            status=status,
            level=level,
        ),
    ]


HANDLERS: Mapping[type[Fact], Callable[[RunLog, Any], Records]] = {
    RunStarted: _run_started,
    RunResumed: _run_resumed,
    RunFinished: _run_finished,
    SeedMeasured: _baseline,
    TrialStarted: _trial_started,
    ModelRequested: _model_requested,
    ModelCalled: _model_called,
    ProposalReceived: _proposal,
    TrialRetried: _retried,
    TrialAbandoned: _abandoned,
    PatchRejected: _rejected,
    CandidateBuilt: _built,
    TrialMeasured: _measured,
}
