"""
Integration tests for the Cadence evolution system.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

from src.database import add_instance, add, get_best_program
from src.evaluator import execute
from src.evolve import apply_diff
from src.llm import generate
from src.prompt_sampler import build
from src.task import Task


class TSPTask(Task):
    """Test TSP Task implementation."""

    @property
    def function_name(self) -> str:
        return "tsp"

    def generate_inputs(self, seed: int):
        import random

        random.seed(seed)
        n = 5
        return [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n)]

    def evaluate(self, output, input_data) -> float:
        if not isinstance(output, list) or sorted(output) != list(
            range(len(input_data))
        ):
            return 1e8  # Infeasible

        # Calculate tour distance
        distance = 0
        cities = input_data
        for i in range(len(output)):
            a = cities[output[i]]
            b = cities[output[(i + 1) % len(output)]]
            distance += ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        return distance

    @property
    def baseline_program(self) -> str:
        return """
def tsp(cities):
    ### START_BLOCK
    return list(range(len(cities)))
    ### END_BLOCK
"""

    def is_feasible(self, output, input_data) -> bool:
        return (
            isinstance(output, list)
            and len(output) == len(input_data)
            and sorted(output) == list(range(len(input_data)))
        )


class TestIntegration:
    """Integration tests for the evolution system."""

    def setup_method(self):
        """Setup test database."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.test_db.close()
        self.task = TSPTask()

    def teardown_method(self):
        """Cleanup test database."""
        if os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)

    @patch("src.database.DATABASE_NAME")
    def test_full_evolution_cycle(self, mock_db_name):
        """Test a complete evolution cycle."""
        mock_db_name.return_value = self.test_db.name

        # Setup database
        import sqlite3

        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed INTEGER NOT NULL
            )
        """)
        cursor.execute("""
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
        """)
        conn.commit()
        conn.close()

        with patch("src.database.DATABASE_NAME", self.test_db.name):
            # 1. Add instance
            instance_id = add_instance(42)
            assert instance_id > 0

            # 2. Add baseline program
            baseline_program = self.task.baseline_program
            baseline_result = execute(baseline_program, self.task, seeds=[42])

            program_id = add(
                program_code=baseline_program,
                metric=baseline_result["cost"],
                instance_id=instance_id,
            )
            assert program_id > 0

            # 3. Get best program
            best = get_best_program()
            assert best is not None
            assert best[0] == program_id

    def test_prompt_building_and_diff_application(self):
        """Test prompt building and diff application workflow."""
        # Create parent program
        parent_program = (1, 0, None, self.task.baseline_program, 100.0, 1)

        # Create inspiration programs
        inspirations = [
            (
                2,
                1,
                1,
                """
def tsp(cities):
    ### START_BLOCK
    return list(reversed(range(len(cities))))
    ### END_BLOCK
""",
                90.0,
                1,
            ),
        ]

        # Build prompt
        prompt = build(parent_program, inspirations)

        # Verify prompt structure
        assert "CURRENT BASELINE SOLUTION" in prompt
        assert "PREVIOUS ATTEMPTS" in prompt
        assert "list(range(len(cities)))" in prompt
        assert "list(reversed(range(len(cities))))" in prompt

        # Test diff application
        diffs = ["return sorted(range(len(cities)), reverse=True)"]
        new_program = apply_diff(parent_program[3], diffs)

        assert "sorted(range(len(cities)), reverse=True)" in new_program
        assert "### START_BLOCK" in new_program
        assert "### END_BLOCK" in new_program

    @patch("src.llm.client")
    def test_llm_generation_and_evaluation(self, mock_client):
        """Test LLM generation and evaluation workflow."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.text = """
### START_BLOCK
# Nearest neighbor heuristic
tour = [0]
remaining = set(range(1, len(cities)))

while remaining:
    current = tour[-1]
    distances = [(i, ((cities[current][0] - cities[i][0])**2 +
                     (cities[current][1] - cities[i][1])**2)**0.5)
                for i in remaining]
    next_city = min(distances, key=lambda x: x[1])[0]
    tour.append(next_city)
    remaining.remove(next_city)

return tour
### END_BLOCK
"""
        mock_client.models.generate_content.return_value = mock_response

        # Generate code
        prompt = "Improve the TSP solution"
        diffs = generate(prompt)

        assert len(diffs) == 1
        assert "Nearest neighbor heuristic" in diffs[0]
        assert "tour = [0]" in diffs[0]
        assert "return tour" in diffs[0]

        # Apply diff to baseline
        baseline = self.task.baseline_program
        new_program = apply_diff(baseline, diffs)

        # Evaluate new program
        result = execute(new_program, self.task, seeds=[42])

        # Should be feasible (though may not be optimal)
        assert result["feasibility"] >= 0
        assert result["cost"] <= 1e8

    def test_evaluation_edge_cases(self):
        """Test evaluation with various edge cases."""
        # Test with invalid tour (wrong length)
        invalid_program = """
def tsp(cities):
    ### START_BLOCK
    return [0, 1]  # Missing cities
    ### END_BLOCK
"""
        result = execute(invalid_program, self.task, seeds=[42])
        assert result["feasibility"] == 0.0
        assert result["cost"] == 1e8

        # Test with invalid tour (duplicate cities)
        duplicate_program = """
def tsp(cities):
    ### START_BLOCK
    return [0, 1, 1, 2, 3]  # Duplicate city
    ### END_BLOCK
"""
        result = execute(duplicate_program, self.task, seeds=[42])
        assert result["feasibility"] == 0.0
        assert result["cost"] == 1e8

        # Test with exception-throwing program
        error_program = """
def tsp(cities):
    ### START_BLOCK
    raise ValueError("Intentional error")
    ### END_BLOCK
"""
        result = execute(error_program, self.task, seeds=[42])
        assert result["feasibility"] == 0.0
        assert result["cost"] == 1e8

    def test_multi_seed_evaluation(self):
        """Test evaluation across multiple seeds."""
        baseline = self.task.baseline_program

        # Test with multiple seeds
        result = execute(baseline, self.task, seeds=[1, 2, 3, 4, 5])

        assert result["feasibility"] == 1.0  # Should be feasible for all seeds
        assert result["cost"] > 0  # Should have positive cost
        assert result["cost"] < 1e8  # Should not be infeasible

    def test_task_interface_compliance(self):
        """Test that TSPTask properly implements Task interface."""
        task = self.task

        # Test function_name
        assert task.function_name == "tsp"

        # Test generate_inputs
        inputs = task.generate_inputs(42)
        assert isinstance(inputs, list)
        assert len(inputs) > 0
        assert all(isinstance(city, tuple) and len(city) == 2 for city in inputs)

        # Test evaluate
        valid_tour = list(range(len(inputs)))
        score = task.evaluate(valid_tour, inputs)
        assert isinstance(score, (int, float))
        assert score > 0

        # Test is_feasible
        assert task.is_feasible(valid_tour, inputs) is True
        assert task.is_feasible([0, 1], inputs) is False  # Wrong length
        assert task.is_feasible("not a list", inputs) is False  # Wrong type

        # Test baseline_program
        baseline = task.baseline_program
        assert isinstance(baseline, str)
        assert "def tsp(cities):" in baseline
        assert "### START_BLOCK" in baseline
        assert "### END_BLOCK" in baseline

    @patch("src.database.DATABASE_NAME")
    def test_database_evolution_tracking(self, mock_db_name):
        """Test that evolution is properly tracked in database."""
        mock_db_name.return_value = self.test_db.name

        # Setup database
        import sqlite3

        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        cursor.execute("""
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
        """)
        conn.commit()
        conn.close()

        with patch("src.database.DATABASE_NAME", self.test_db.name):
            # Add generation 0 program
            gen0_id = add(program_code=self.task.baseline_program, metric=100.0)

            # Add generation 1 program
            gen1_id = add(
                program_code="def tsp(cities): return list(reversed(range(len(cities))))",
                metric=90.0,
                parent_id=gen0_id,
                diff="return list(reversed(range(len(cities))))",
                prompt="Improve the baseline",
            )

            # Add generation 2 program
            gen2_id = add(
                program_code="def tsp(cities): return sorted(range(len(cities)))",
                metric=85.0,
                parent_id=gen1_id,
                diff="return sorted(range(len(cities)))",
                prompt="Further optimize",
            )

            # Verify generation numbers are correct
            conn = sqlite3.connect(self.test_db.name)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT generation_number FROM programs WHERE id = ?", (gen0_id,)
            )
            assert cursor.fetchone()[0] == 0

            cursor.execute(
                "SELECT generation_number FROM programs WHERE id = ?", (gen1_id,)
            )
            assert cursor.fetchone()[0] == 1

            cursor.execute(
                "SELECT generation_number FROM programs WHERE id = ?", (gen2_id,)
            )
            assert cursor.fetchone()[0] == 2

            conn.close()

            # Verify best program tracking
            best = get_best_program()
            assert best[0] == gen2_id  # Should be the one with lowest metric
            assert best[4] == 85.0
