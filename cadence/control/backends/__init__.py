"""Where a prompt goes.

- ``scripted`` -- canned answers, no network and no key
- ``chat`` -- any provider speaking the OpenAI dialect
- ``reliable`` -- retries and audits either of them
- ``wire`` -- the dialect itself
- ``http`` -- posting JSON
- ``settings`` -- providers.yml, and where keys come from
"""

from cadence.control.backends.chat import OpenAIDialect, chat_backend
from cadence.control.backends.reliable import Reliable, Silent
from cadence.control.backends.scripted import Scripted
from cadence.control.backends.settings import known

__all__ = [
    "OpenAIDialect",
    "Reliable",
    "Scripted",
    "Silent",
    "chat_backend",
    "known",
]
