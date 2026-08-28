"""How cadence names things.

A fingerprint is the identity of a piece of code: two candidates with the same
fingerprint are the same program, whichever trial produced them. It is what
dedup, the verdict cache and quarantine are all keyed on, so it lives here
rather than beside any one of them.
"""

from hashlib import sha256

__all__ = ["FINGERPRINT_LENGTH", "fingerprint"]

FINGERPRINT_LENGTH = 16


def fingerprint(code: str) -> str:
    return sha256(code.encode()).hexdigest()[:FINGERPRINT_LENGTH]
