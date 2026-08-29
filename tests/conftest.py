"""Markers, and nothing else.

Every fixture that used to live here served the replaced system: an in-memory
sqlite schema, a fake LLM client, TSP sample data. What the current suite
needs, it builds in tests/factories.py or asks for in the test that wants it.
"""

from typing import Any


def pytest_configure(config: Any) -> None:
    config.addinivalue_line("markers", "integration: needs docker compose up -d")
