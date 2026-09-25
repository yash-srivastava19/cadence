"""Runs and trials, for a person with a browser.

A sibling of `commands`, not a layer under it: both are entry points, both
open a session, ask `control.queries` what happened and hand the answer to
`delivery`. Neither decides anything. The web plane is the CLI's listing
commands with a different way in.

Read-only on purpose. It may not import `execution` and it writes nothing.
The moment a button here can start a run this stops being a dashboard and
becomes a control plane, with leases, ownership and authentication to answer
-- and none of those questions have been answered.
"""

from cadence.web.api import answer
from cadence.web.server import serve

__all__ = ["answer", "serve"]
