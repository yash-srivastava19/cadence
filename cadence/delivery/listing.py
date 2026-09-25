"""Runs and trials, for a person at a terminal.

Columns rather than prose, because the reason to list runs is to compare
them, and comparing means reading down.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from cadence.core.dto import (
    Comparison,
    MetricReading,
    RunDetail,
    RunSummary,
    TrialSummary,
)

__all__ = ["one_as_text", "runs_as_text", "trials_as_text"]

NOTHING = "-"


def _status(row: RunSummary) -> str:
    """What the listing believes, which is not always what the row says.

    A run whose process was killed leaves RUNNING behind and keeps it, so the
    one command for "what is happening" reports things that stopped days ago.
    """
    return "stalled" if row.stalled else str(row.status)


def runs_as_text(rows: Sequence[RunSummary]) -> str:
    if not rows:
        return "no runs"
    return _table(
        ("id", "status", "trials", "best", "experiment", "owner", "started"),
        [
            (
                row.id,
                _status(row),
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
        ("seq", "status", "score", "vs its parent", "attempts", "reason"),
        [
            (
                str(row.seq),
                row.status,
                _scores(row.metrics),
                _against(row),
                str(row.attempts),
                _short(row.reason, 40),
            )
            for row in rows
        ],
    )


def _against(row: TrialSummary) -> str:
    """The lead metric only. The score column already lists them all, and a
    comparison per metric is wider than a terminal."""
    for one in row.compared.values():
        return _said(one)
    return NOTHING


#: Rendered here rather than dumped, and rendered the same way the dashboard
#: renders it. Both read one MetricReading, so the terminal and the browser
#: cannot come to different conclusions about the same run.
SHOWN_APART = {
    "readings",
    "stopped",
    "manifest",
    "directions",
    "baseline",
    "compared",
}


def one_as_text(row: RunSummary | TrialSummary) -> str:
    """One record, down the page. Nothing to compare it with, so no columns."""
    apart = SHOWN_APART | {"reason"} if isinstance(row, RunDetail) else SHOWN_APART
    fields = {
        name: value
        for name, value in row.model_dump(mode="json").items()
        if name not in apart
    }
    width = max(len(name) for name in fields)
    lines = [
        f"{name:<{width}}  {NOTHING if value is None else value}"
        for name, value in fields.items()
    ]
    if isinstance(row, RunDetail):
        lines.extend(_run_apart(row))
    return "\n".join(lines)


def _aim(direction: str | None) -> str:
    if direction == "minimize":
        return "lower is better"
    if direction == "maximize":
        return "higher is better"
    return "no direction declared"


def _said(comparison: Comparison) -> str:
    if comparison.judgment == "same":
        return f"no change vs {comparison.referent}"
    size = f"{comparison.delta:+.4g}"
    if comparison.percent is not None:
        size += f" ({comparison.percent:.1f}%)"
    return f"{size} {comparison.judgment} vs {comparison.referent}"


def _reading(reading: MetricReading) -> list[str]:
    out = [f"\n{reading.name}  {_aim(reading.direction)}"]
    if reading.best is None:
        out.append("  nothing scored")
        return out
    best = f"  best      {reading.best:g}  at trial {reading.best_at}"
    if reading.vs_baseline:
        best += f"  {_said(reading.vs_baseline)}"
    out.append(best)
    if reading.off_best:
        out.append(
            f"  latest    {reading.latest:g}  at trial {reading.latest_at}"
            f"  {_said(reading.off_best)}"
        )
    out.append(
        f"  records   {reading.records} new best"
        f"{'' if reading.records == 1 else 's'} in {reading.scored} scored,"
        f" {reading.since_best} since the last one"
    )
    return out


def _run_apart(run: RunDetail) -> list[str]:
    lines: list[str] = []
    for reading in run.readings:
        lines.extend(_reading(reading))
    if run.stopped:
        lines.append(f"\n{run.stopped.lead}")
        if run.stopped.detail:
            lines.append(f"  {run.stopped.detail}")
    return lines


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
