"""Where a prompt goes.

    scripted.py   canned answers, no network, no key
    chat.py       any provider speaking the OpenAI dialect
    reliable.py   retries and audits either of them
    wire.py       the dialect itself
    http.py       posting JSON
    settings.py   providers.yml, and where keys come from
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
