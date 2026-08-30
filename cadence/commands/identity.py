"""Who ran this, and what to call it.

Both are about the invocation rather than the experiment, which is why they
are decided here and not in the manifest: the same .cadence run by two people
is two runs by two owners.
"""

import os
import secrets
import subprocess
from datetime import UTC, datetime

__all__ = ["fresh_id", "owner"]


def fresh_id() -> str:
    """A run id nobody else will pick.

    Sortable first so a listing reads in the order things happened, random
    last so two runs started in the same second still differ.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(3)}"


def owner() -> str | None:
    """Who to credit a run to.

    The git address first, because it is the same identity as the pull
    request the run is evidence for. CADENCE_OWNER wins for anywhere that
    identity is wrong -- CI, a shared box, a cluster node.
    """
    return os.environ.get("CADENCE_OWNER") or _git_email() or os.environ.get("USER")


def _git_email() -> str | None:
    try:
        found = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None  # no git on this machine
    return found.stdout.strip() or None
