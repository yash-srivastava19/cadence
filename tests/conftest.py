"""
Enhanced configuration for pytest with comprehensive fixtures.

This module provides typed fixtures and configuration for testing
the Cadence evolution system with proper type safety.
"""

import os
import sqlite3
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from tests.fixtures.mock_responses import MOCK_RESPONSES, MockLLMClient
from tests.fixtures.sample_code import (
    SAMPLE_CITIES_4,
    SAMPLE_CITIES_10,
    SAMPLE_TSP_BASELINE,
    SAMPLE_TSP_IMPROVED,
)


@pytest.fixture
def temp_database() -> Generator[sqlite3.Connection, None, None]:
    """Create a temporary in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create tables matching the real schema
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed INTEGER NOT NULL
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            instance_id INTEGER,
            generation_number INTEGER,
            program_code TEXT NOT NULL,
            metric REAL,
            diff TEXT,
            prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES programs(id),
            FOREIGN KEY (instance_id) REFERENCES instances(id)
        )
    """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def temp_db_file() -> Generator[str, None, None]:
    """Provide a temporary database file for testing."""
    # The fixture owns this for its whole life, so it cannot live in a
    # with-block; it is closed below and removed on teardown.
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")  # noqa: SIM115
    temp_db.close()

    yield temp_db.name

    # Cleanup
    if os.path.exists(temp_db.name):
        os.unlink(temp_db.name)


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Create a mock LLM client for testing."""
    return MockLLMClient()


@pytest.fixture
def mock_llm_generate() -> Generator[Any, None, None]:
    """Mock LLM generate function."""
    with patch("src.llm.generate") as mock:
        mock.return_value = [MOCK_RESPONSES["simple_improvement"]]
        yield mock


@pytest.fixture
def tsp_task():
    """Create a TSP task instance for testing."""
    from src.tasks.tsp_task import TSPTask

    return TSPTask()


@pytest.fixture
def sample_cities_4() -> list[tuple[float, float]]:
    """Sample 4-city TSP instance."""
    return SAMPLE_CITIES_4


@pytest.fixture
def sample_cities_10() -> list[tuple[float, float]]:
    """Sample 10-city TSP instance."""
    return SAMPLE_CITIES_10


@pytest.fixture
def sample_baseline_program() -> str:
    """Sample baseline TSP program."""
    return SAMPLE_TSP_BASELINE


@pytest.fixture
def sample_improved_program() -> str:
    """Sample improved TSP program."""
    return SAMPLE_TSP_IMPROVED


@pytest.fixture
def sample_tsp_program() -> str:
    """Provide a sample TSP program for testing (legacy compatibility)."""
    return SAMPLE_TSP_IMPROVED


@pytest.fixture
def sample_cities() -> list[tuple[float, float]]:
    """Provide sample city coordinates for testing."""
    return [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.5, 0.5)]


# Configure pytest settings
def pytest_configure(config: Any) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "llm: mark test as requiring LLM API")


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Add markers to tests based on their names."""
    for item in items:
        # Mark integration tests
        if "integration" in item.name or "test_integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark LLM tests
        if "llm" in item.name or "test_llm" in str(item.fspath):
            item.add_marker(pytest.mark.llm)

        # Mark slow tests
        if any(
            word in item.name for word in ["full_evolution", "multi_seed", "concurrent"]
        ):
            item.add_marker(pytest.mark.slow)
