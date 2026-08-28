"""How cadence names things.

A fingerprint is the identity of a piece of code: two candidates with the same
fingerprint are the same program, whichever trial produced them. It is what
dedup, the verdict cache and quarantine are all keyed on, so it lives here
rather than beside any one of them.
"""

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

__all__ = ["FINGERPRINT_LENGTH", "fingerprint", "hash_of"]

FINGERPRINT_LENGTH = 16


def fingerprint(code: str) -> str:
    return sha256(code.encode()).hexdigest()[:FINGERPRINT_LENGTH]


def hash_of(document: Mapping[str, Any]) -> str:
    """The identity of a configuration, as its canonical JSON.

    Sorted keys and no incidental whitespace, so that two documents cadence
    would act on identically hash identically -- which is the whole point of
    storing the hash beside a result.
    """
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()[:FINGERPRINT_LENGTH]
