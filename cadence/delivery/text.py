"""A finished run, for a person."""

from cadence.core.dto import Report, Spend

__all__ = ["as_text"]


def as_text(report: Report) -> str:
    lines = [
        f"{report.status}  {report.scored}/{report.trials} scored",
        spent(report.spend),
    ]
    if report.reason:
        lines.append(f"\n{report.reason}")
    for name, value in (report.metrics or {}).items():
        lines.append(f"  {name} = {value:g}")
    if report.program:
        lines.append(f"\n{report.program}")
    return "\n".join(lines)


def spent(spend: Spend) -> str:
    """What it cost. A result without one cannot be compared with another."""
    replayed = f", {spend.replayed} replayed" if spend.replayed else ""
    return (
        f"{spend.calls} model call{'s' if spend.calls != 1 else ''}{replayed},"
        f" {spend.tokens:,} tokens"
        f" ({spend.tokens_in:,} in, {spend.tokens_out:,} out)"
    )
