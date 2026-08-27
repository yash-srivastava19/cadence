"""
Tests for the database module.
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

from src.database import (
    add,
    add_instance,
    get_best_program,
    sample,
)


class TestDatabase:
    """Test database operations."""

    def setup_method(self):
        """Setup test database."""
        # Owned across the whole test, so it cannot live in a with-block.
        self.test_db = tempfile.NamedTemporaryFile(  # noqa: SIM115
            delete=False, suffix=".db"
        )
        self.test_db.close()

    def teardown_method(self):
        """Cleanup test database."""
        if os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)

    @patch("src.database.DATABASE_NAME")
    def test_add_instance(self, mock_db_name):
        """Test adding an instance."""
        mock_db_name.return_value = self.test_db.name

        # Create tables manually for test
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed INTEGER NOT NULL
            )
        """
        )
        conn.commit()
        conn.close()

        # Test adding instance
        with patch("src.database.DATABASE_NAME", self.test_db.name):
            instance_id = add_instance(42)
            assert instance_id > 0

            # Verify it was added
            conn = sqlite3.connect(self.test_db.name)
            cursor = conn.cursor()
            cursor.execute("SELECT seed FROM instances WHERE id = ?", (instance_id,))
            result = cursor.fetchone()
            conn.close()

            assert result[0] == 42

    @patch("src.database.DATABASE_NAME")
    def test_add_program(self, mock_db_name):
        """Test adding a program."""
        mock_db_name.return_value = self.test_db.name

        # Setup tables
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
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
        conn.close()

        with patch("src.database.DATABASE_NAME", self.test_db.name):
            # Test adding root program
            program_id = add(
                program_code="def test(): pass",
                metric=100.0,
                diff="test diff",
                prompt="test prompt",
            )
            assert program_id > 0

            # Test adding child program
            child_id = add(
                program_code="def test_child(): pass",
                metric=50.0,
                parent_id=program_id,
                diff="child diff",
                prompt="child prompt",
            )
            assert child_id > 0

            # Verify generation numbers
            conn = sqlite3.connect(self.test_db.name)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT generation_number FROM programs WHERE id = ?", (program_id,)
            )
            parent_gen = cursor.fetchone()[0]
            cursor.execute(
                "SELECT generation_number FROM programs WHERE id = ?", (child_id,)
            )
            child_gen = cursor.fetchone()[0]
            conn.close()

            assert parent_gen == 0
            assert child_gen == 1

    @patch("src.database.DATABASE_NAME")
    def test_get_best_program(self, mock_db_name):
        """Test getting best program."""
        mock_db_name.return_value = self.test_db.name

        # Setup tables and data
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Insert test data
        cursor.execute(
            """
            INSERT INTO programs (program_code, metric, generation_number)
            VALUES ('code1', 100.0, 0)
        """
        )
        cursor.execute(
            """
            INSERT INTO programs (program_code, metric, generation_number)
            VALUES ('code2', 50.0, 1)
        """
        )
        cursor.execute(
            """
            INSERT INTO programs (program_code, metric, generation_number)
            VALUES ('code3', 75.0, 2)
        """
        )
        conn.commit()
        conn.close()

        with patch("src.database.DATABASE_NAME", self.test_db.name):
            best = get_best_program()
            assert best is not None
            assert best[4] == 50.0  # metric should be 50.0

            # Test with generation limit
            best_limited = get_best_program(generation_limit=0)
            assert best_limited[4] == 100.0  # Should be first program

    @patch("src.database.DATABASE_NAME")
    def test_sample(self, mock_db_name):
        """Test sampling programs."""
        mock_db_name.return_value = self.test_db.name

        # Setup tables and data
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Insert parent
        cursor.execute(
            """
            INSERT INTO programs (program_code, metric, generation_number)
            VALUES ('parent_code', 100.0, 0)
        """
        )
        parent_id = cursor.lastrowid

        # Insert children
        cursor.execute(
            """
            INSERT INTO programs (parent_id, program_code, metric, generation_number)
            VALUES (?, 'child1_code', 80.0, 1)
        """,
            (parent_id,),
        )
        cursor.execute(
            """
            INSERT INTO programs (parent_id, program_code, metric, generation_number)
            VALUES (?, 'child2_code', 90.0, 1)
        """,
            (parent_id,),
        )

        conn.commit()
        conn.close()

        with patch("src.database.DATABASE_NAME", self.test_db.name):
            parent, children = sample(generation_number=0)
            assert parent is not None
            assert len(children) == 2
            assert parent[1] == 0  # generation_number
            assert all(child[2] == parent[0] for child in children)  # parent_id matches
