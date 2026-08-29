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
    """What it cost. A result without one cannot be compared with another.

    Money last and only when there is a price for it, because it is the
    number a reader stops at: best-found is incomparable between two runs
    that spent differently, and tokens are incomparable between two models.
    """
    replayed = f", {spend.replayed} replayed" if spend.replayed else ""
    return (
        f"{spend.calls} model call{'s' if spend.calls != 1 else ''}{replayed},"
        f" {spend.tokens:,} tokens"
        f" ({spend.tokens_in:,} in, {spend.tokens_out:,} out)"
        f"{billed(spend)}"
    )


def billed(spend: Spend) -> str:
    """The dollars, and what they do not include.

    Replays are named because calls and tokens count them and this does not:
    "3 calls, $0.0021" invites dividing one by the other, and the answer would
    be wrong for any run that read an answer back instead of buying it.
    """
    if spend.usd is None:
        return ""
    if spend.replayed:
        return (
            f", ${spend.usd:.4f} billed for the {spend.calls - spend.replayed} bought"
        )
    return f", ${spend.usd:.4f}"
