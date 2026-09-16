"""The dashboard itself: one HTML file, no build step, no dependencies.

Read from disk on every request rather than held as a string in this module.
A page baked in at import time means every edit to the markup needs the
server restarted to see it, which is the wrong trade for a file whose whole
job is to be looked at and adjusted. The read is a few kilobytes against a
request that is already going to talk to Postgres.

Nothing is filled in from Python. Every number on the page arrives over the
same JSON `cadence runs list --json` prints, fetched after the page loads,
which is why there is exactly one place where a shape is decided and it is
`core/dto.py`.
"""

from pathlib import Path

__all__ = ["VENDOR", "page"]

HERE = Path(__file__).parent / "page.html"

VENDOR = Path(__file__).parent / "vendor"


def page() -> str:
    return HERE.read_text(encoding="utf-8")
