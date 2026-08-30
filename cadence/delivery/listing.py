"""Runs and trials, for a person at a terminal.

Columns rather than prose, because the reason to list runs is to compare
them, and comparing means reading down.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from cadence.core.dto import RunSummary, TrialSummary

__all__ = ["one_as_text", "runs_as_text", "trials_as_text"]

NOTHING = "-"


def runs_as_text(rows: Sequence[RunSummary]) -> str:
    if not rows:
        return "no runs"
    return _table(
        ("id", "status", "trials", "best", "experiment", "owner", "started"),
        [
            (
                row.id,
                row.status,
                str(row.trials),
                _short(row.best),
                row.experiment or NOTHING,
                _short(row.owner, 24),
                _when(row.started_at),
            )
            for row in rows
        ],
    )


def trials_as_text(rows: Sequence[TrialSummary]) -> str:
    if not rows:
        return "no trials"
    return _table(
        ("seq", "status", "score", "attempts", "candidate", "reason"),
        [
            (
                str(row.seq),
                row.status,
                _scores(row.metrics),
                str(row.attempts),
                _short(row.candidate),
                _short(row.reason, 40),
            )
            for row in rows
        ],
    )


def one_as_text(row: RunSummary | TrialSummary) -> str:
    """One record, down the page. Nothing to compare it with, so no columns."""
    fields = row.model_dump(mode="json")
    width = max(len(name) for name in fields)
    return "\n".join(
        f"{name:<{width}}  {NOTHING if value is None else value}"
        for name, value in fields.items()
    )


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [
        max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)
    ]
    lines = [_row(headers, widths), _row(["-" * w for w in widths], widths)]
    lines.extend(_row(row, widths) for row in rows)
    return "\n".join(lines)


def _row(cells: Sequence[str], widths: Sequence[int]) -> str:
    padded = zip(cells, widths, strict=True)
    return "  ".join(cell.ljust(width) for cell, width in padded).rstrip()


def _scores(metrics: Mapping[str, float] | None) -> str:
    """The numbers, and which is which. One metric is the common case and
    prints bare; several are named, or the columns would not line up."""
    if not metrics:
        return NOTHING
    if len(metrics) == 1:
        [value] = metrics.values()
        return f"{value:g}"
    return " ".join(f"{name}={value:g}" for name, value in sorted(metrics.items()))


def _short(value: str | None, keep: int = 12) -> str:
    """Hashes are 64 characters and no two differ in the last 50."""
    if not value:
        return NOTHING
    return value if len(value) <= keep else value[:keep] + "…"


def _when(value: datetime | None) -> str:
    return NOTHING if value is None else value.strftime("%Y-%m-%d %H:%M")
