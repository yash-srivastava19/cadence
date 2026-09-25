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

__all__ = ["VENDOR", "page", "version"]

HERE = Path(__file__).parent / "page.html"

VENDOR = Path(__file__).parent / "vendor"


def page() -> str:
    return HERE.read_text(encoding="utf-8")


def version() -> str:
    """When the page was last written, so an open tab can notice.

    The page is already read from disk on every request, so editing it and
    reloading works; this is the half that saves the reload. Cheap enough to
    ask for every couple of seconds: one stat call against a local file.
    """
    return str(HERE.stat().st_mtime_ns)
