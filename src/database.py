"""
Database module for Cadence evolution system.

This module provides a typed interface to SQLite database operations
with Pydantic model validation and comprehensive error handling.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager

from .models import (
    ProgramEntry,
    TaskInstance,
    DatabaseConfig,
    GenerationSummary,
    ProgramCode,
    MetricValue,
)

# Type aliases for database rows
ProgramRow = Tuple[
    int,
    int,
    Optional[int],
    str,
    float,
    Optional[int],
    Optional[str],
    Optional[str],
    str,
]
InstanceRow = Tuple[int, int]

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""

    pass


class Database:
    """
    Main database interface for Cadence evolution system.

    Provides typed methods for storing and retrieving programs,
    instances, and experimental results.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        """
        Initialize database connection.

        Args:
            config: Database configuration, uses defaults if None
        """
        if config is None:
            config = DatabaseConfig()

        self.config = config
        self.db_path = Path(config.database_path)
        self._ensure_database_exists()
        self._create_tables()

    def _ensure_database_exists(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path), timeout=self.config.connection_timeout
            )
            if self.config.enable_wal_mode:
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise DatabaseError(f"Database operation failed: {e}")
        finally:
            if conn:
                conn.close()

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Instances table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed INTEGER NOT NULL,
                    task_type TEXT NOT NULL,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Programs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS programs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    instance_id INTEGER,
                    generation_number INTEGER NOT NULL,
                    program_code TEXT NOT NULL,
                    metric REAL NOT NULL,
                    diff TEXT,
                    prompt TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES programs(id),
                    FOREIGN KEY (instance_id) REFERENCES instances(id)
                )
            """
            )

            # Experiments table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create indexes for performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_programs_generation
                ON programs(generation_number)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_programs_metric
                ON programs(metric)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_programs_parent
                ON programs(parent_id)
            """
            )

            conn.commit()

    def add_instance(self, instance: TaskInstance) -> int:
        """
        Add a task instance to the database.

        Args:
            instance: TaskInstance to store

        Returns:
            Database ID of the stored instance

        Raises:
            DatabaseError: If storage fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                try:
                    # Primary insert with full schema
                    cursor.execute(
                        """
                        INSERT INTO instances (seed, task_type, data_json)
                        VALUES (?, ?, ?)
                    """,
                        (
                            instance.seed,
                            instance.task_type.value,
                            instance.model_dump_json(),
                        ),
                    )
                except sqlite3.OperationalError as oe:
                    # Fallback for minimal schema (e.g., tests) with only seed column
                    if "no column named task_type" in str(
                        oe
                    ) or "no column named data_json" in str(oe):
                        cursor.execute(
                            "INSERT INTO instances (seed) VALUES (?)", (instance.seed,)
                        )
                    else:
                        raise
                instance_id = cursor.lastrowid
                conn.commit()
                logger.debug(f"Added instance {instance_id} with seed {instance.seed}")
                return instance_id
        except Exception as e:
            raise DatabaseError(f"Failed to add instance: {e}")

    def add_program(
        self,
        code: ProgramCode,
        metric: MetricValue,
        generation: int,
        parent_id: Optional[int] = None,
        instance_id: Optional[int] = None,
        diff: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> int:
        """
        Add a program to the database.

        Args:
            code: Program source code
            metric: Performance metric (lower is better)
            generation: Generation number
            parent_id: ID of parent program
            instance_id: ID of test instance
            diff: Code diff from parent
            prompt: Generation prompt

        Returns:
            Database ID of the stored program

        Raises:
            DatabaseError: If storage fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO programs (
                        parent_id, instance_id, generation_number,
                        program_code, metric, diff, prompt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        parent_id,
                        instance_id,
                        generation,
                        code,
                        float(metric),
                        diff,
                        prompt,
                    ),
                )

                program_id = cursor.lastrowid
                conn.commit()

                logger.debug(f"Added program {program_id} in generation {generation}")
                return program_id

        except Exception as e:
            raise DatabaseError(f"Failed to add program: {e}")

    def get_program(self, program_id: int) -> Optional[ProgramEntry]:
        """
        Get a program by ID.

        Args:
            program_id: Program database ID

        Returns:
            ProgramEntry if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, generation_number, parent_id, program_code,
                           metric, instance_id, diff, prompt, created_at
                    FROM programs WHERE id = ?
                """,
                    (program_id,),
                )

                row = cursor.fetchone()
                if row:
                    return ProgramEntry(
                        id=row[0],
                        generation=row[1],
                        parent_id=row[2],
                        code=row[3],
                        metric=row[4],
                        instance_id=row[5],
                        diff=row[6],
                        prompt=row[7],
                        timestamp=row[8],
                    )
                return None

        except Exception as e:
            logger.error(f"Failed to get program {program_id}: {e}")
            return None

    def sample_parent(self, generation: int = 0) -> Optional[ProgramEntry]:
        """
        Sample a random parent program from a generation.

        Args:
            generation: Generation number to sample from

        Returns:
            Random ProgramEntry from the generation, None if none exist
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, generation_number, parent_id, program_code,
                           metric, instance_id, diff, prompt, created_at
                    FROM programs
                    WHERE generation_number = ?
                    ORDER BY RANDOM()
                    LIMIT 1
                """,
                    (generation,),
                )

                row = cursor.fetchone()
                if row:
                    return ProgramEntry(
                        id=row[0],
                        generation=row[1],
                        parent_id=row[2],
                        code=row[3],
                        metric=row[4],
                        instance_id=row[5],
                        diff=row[6],
                        prompt=row[7],
                        timestamp=row[8],
                    )
                return None

        except Exception as e:
            logger.error(f"Failed to sample parent from generation {generation}: {e}")
            return None

    def get_children(self, parent_id: int) -> List[ProgramEntry]:
        """
        Get all children of a parent program.

        Args:
            parent_id: Parent program ID

        Returns:
            List of child ProgramEntry objects
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, generation_number, parent_id, program_code,
                           metric, instance_id, diff, prompt, created_at
                    FROM programs
                    WHERE parent_id = ?
                    ORDER BY metric ASC
                """,
                    (parent_id,),
                )

                rows = cursor.fetchall()
                return [
                    ProgramEntry(
                        id=row[0],
                        generation=row[1],
                        parent_id=row[2],
                        code=row[3],
                        metric=row[4],
                        instance_id=row[5],
                        diff=row[6],
                        prompt=row[7],
                        timestamp=row[8],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get children of program {parent_id}: {e}")
            return []

    def get_best_program(
        self, generation_limit: Optional[int] = None
    ) -> Optional[ProgramEntry]:
        """
        Get the best program (lowest metric) from the database.

        Args:
            generation_limit: Only consider programs up to this generation

        Returns:
            Best ProgramEntry if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if generation_limit is not None:
                    cursor.execute(
                        """
                        SELECT id, generation_number, parent_id, program_code,
                               metric, instance_id, diff, prompt, created_at
                        FROM programs
                        WHERE generation_number <= ?
                        ORDER BY metric ASC
                        LIMIT 1
                    """,
                        (generation_limit,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id, generation_number, parent_id, program_code,
                               metric, instance_id, diff, prompt, created_at
                        FROM programs
                        ORDER BY metric ASC
                        LIMIT 1
                    """
                    )

                row = cursor.fetchone()
                if row:
                    return ProgramEntry(
                        id=row[0],
                        generation=row[1],
                        parent_id=row[2],
                        code=row[3],
                        metric=row[4],
                        instance_id=row[5],
                        diff=row[6],
                        prompt=row[7],
                        timestamp=row[8],
                    )
                return None

        except Exception as e:
            logger.error(f"Failed to get best program: {e}")
            return None

    def get_generation_summary(self, generation: int) -> Optional[GenerationSummary]:
        """
        Get summary statistics for a generation.

        Args:
            generation: Generation number

        Returns:
            GenerationSummary if generation exists, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT COUNT(*), MIN(metric), AVG(metric), MAX(metric),
                           SUM(CASE WHEN metric < ? THEN 1 ELSE 0 END)
                    FROM programs
                    WHERE generation_number = ?
                """,
                    (1e7, generation),
                )  # Assume costs < 1e7 are feasible

                row = cursor.fetchone()
                if row and row[0] > 0:
                    return GenerationSummary(
                        generation=generation,
                        program_count=row[0],
                        best_cost=row[1],
                        average_cost=row[2],
                        worst_cost=row[3],
                        feasible_count=row[4],
                    )
                return None

        except Exception as e:
            logger.error(f"Failed to get generation {generation} summary: {e}")
            return None

    def get_all_programs(self) -> List[ProgramEntry]:
        """
        Get all programs from the database.

        Returns:
            List of all ProgramEntry objects
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, generation_number, parent_id, program_code,
                           metric, instance_id, diff, prompt, created_at
                    FROM programs
                    ORDER BY generation_number, metric ASC
                """
                )

                rows = cursor.fetchall()
                return [
                    ProgramEntry(
                        id=row[0],
                        generation=row[1],
                        parent_id=row[2],
                        code=row[3],
                        metric=row[4],
                        instance_id=row[5],
                        diff=row[6],
                        prompt=row[7],
                        timestamp=row[8],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get all programs: {e}")
            return []

    def create_run(self, run_id: str, experiment_config: str) -> None:
        """
        Create a new experiment run record.

        Args:
            run_id: Unique run identifier
            experiment_config: JSON configuration string
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO experiments (id, config_json, status, start_time)
                    VALUES (?, ?, ?, ?)
                """,
                    (run_id, experiment_config, "running", datetime.now().isoformat()),
                )

                conn.commit()
                logger.info(f"Created experiment run {run_id}")

        except Exception as e:
            raise DatabaseError(f"Failed to create run: {e}")

    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of an experiment run.

        Args:
            run_id: Run identifier

        Returns:
            Dictionary with run summary or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT config_json, status, start_time, end_time
                    FROM experiments WHERE id = ?
                """,
                    (run_id,),
                )

                row = cursor.fetchone()
                if row:
                    return {
                        "run_id": run_id,
                        "config": row[0],
                        "status": row[1],
                        "start_time": row[2],
                        "end_time": row[3],
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get run summary for {run_id}: {e}")
            return None


# Legacy functions for backwards compatibility
DATABASE_NAME: str = "cadence_db.sqlite"


def add_instance(seed: int) -> int:
    """Legacy function - add instance."""
    from .models import TaskInstance, TaskType

    instance = TaskInstance(
        id=0,  # Will be overridden
        seed=seed,
        task_type=TaskType.TSP,
        data={"seed": seed},
    )
    # Use fresh Database instance to respect patched DATABASE_NAME
    from .models import DatabaseConfig

    db = Database(DatabaseConfig(database_path=DATABASE_NAME))
    return db.add_instance(instance)


def add(
    program_code: str,
    metric: float,
    parent_id: Optional[int] = None,
    instance_id: Optional[int] = None,
    diff: Optional[str] = None,
    prompt: Optional[str] = None,
) -> int:
    """Legacy function - add program."""
    generation = 0
    from .models import DatabaseConfig

    db = Database(DatabaseConfig(database_path=DATABASE_NAME))
    if parent_id is not None:
        parent = db.get_program(parent_id)
        if parent:
            generation = parent.generation + 1

    from .models import DatabaseConfig

    db = Database(DatabaseConfig(database_path=DATABASE_NAME))
    return db.add_program(
        program_code, metric, generation, parent_id, instance_id, diff, prompt
    )


def sample(generation_number: int = 0) -> Tuple[Optional[Tuple], List[Tuple]]:
    """Legacy function - sample parent and get children."""
    from .models import DatabaseConfig

    db = Database(DatabaseConfig(database_path=DATABASE_NAME))
    parent = db.sample_parent(generation_number)
    if parent:
        children = db.get_children(parent.id)
        parent_tuple = (
            parent.id,
            parent.generation,
            parent.parent_id,
            parent.code,
            parent.metric,
        )
        children_tuples = [
            (c.id, c.generation, c.parent_id, c.code, c.metric) for c in children
        ]
        return parent_tuple, children_tuples
    return None, []


def get_best_program(generation_limit: Optional[int] = None) -> Optional[Tuple]:
    """Legacy function - get best program."""
    from .models import DatabaseConfig

    db = Database(DatabaseConfig(database_path=DATABASE_NAME))
    program = db.get_best_program(generation_limit)
    if program:
        return (
            program.id,
            program.generation,
            program.parent_id,
            program.code,
            program.metric,
        )
    return None


def get_all_programs() -> List[Tuple]:
    """Legacy function - get all programs."""
    from .models import DatabaseConfig

    db = Database(DatabaseConfig(database_path=DATABASE_NAME))
    programs = db.get_all_programs()
    return [
        (p.id, p.generation, p.parent_id, p.code, p.metric, p.diff, p.prompt)
        for p in programs
    ]
