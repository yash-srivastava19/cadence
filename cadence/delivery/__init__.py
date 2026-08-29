"""Turning a result into something to read.

The only plane that knows how output looks. Nothing below it returns a string
meant for a person, and nothing in it decides what happened -- which is what
lets one Report be shown as two-column text to someone at a terminal and as
JSON to whatever comes next.
"""

from cadence.delivery.json import as_json
from cadence.delivery.text import as_text

__all__ = ["as_json", "as_text"]
