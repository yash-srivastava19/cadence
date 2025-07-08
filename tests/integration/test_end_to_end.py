"""End-to-end integration tests for the Cadence system."""

import pytest
import tempfile
from pathlib import Path

from src.database import Database
from src.evaluator import Evaluator
from src.evolve import Evolver
from src.task import TaskManager
from src.tasks.tsp import TSPTask


class TestEndToEndEvolution:
    """Test complete evolution workflows."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def evolution_system(self, temp_db_path, mock_llm_provider):
        """Set up a complete evolution system."""
        db = Database(temp_db_path)
        evaluator = Evaluator()
        evolver = Evolver(mock_llm_provider, db)
        task_manager = TaskManager()

        return {
            "database": db,
            "evaluator": evaluator,
            "evolver": evolver,
            "task_manager": task_manager,
            "llm": mock_llm_provider,
        }

    def test_complete_evolution_cycle(self, evolution_system):
        """Test a complete evolution cycle from start to finish."""
        system = evolution_system

        # Register a simple TSP task
        tsp_task = TSPTask(cities=5)
        system["task_manager"].register_task("simple_tsp", tsp_task)

        # Create initial code
        initial_code = """
def solve_tsp(cities):
    # Simple nearest neighbor heuristic
    if len(cities) <= 1:
        return cities

    unvisited = set(range(1, len(cities)))
    tour = [0]
    current = 0

    while unvisited:
        nearest = min(unvisited, key=lambda x: distance(cities[current], cities[x]))
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return tour

def distance(city1, city2):
    return ((city1[0] - city2[0])**2 + (city1[1] - city2[1])**2)**0.5
"""

        # Evaluate initial code
        result = system["evaluator"].evaluate_code(initial_code, tsp_task)
        assert result is not None
        assert "fitness" in result

        # Store in database
        run_id = system["database"].create_run("test_evolution", "simple_tsp")
        system["database"].store_generation(run_id, 0, [result])

        # Evolve the code
        evolved_code = system["evolver"].evolve_code(
            initial_code, result, tsp_task, generation=1
        )

        assert evolved_code != initial_code
        assert len(evolved_code) > 0

        # Evaluate evolved code
        evolved_result = system["evaluator"].evaluate_code(evolved_code, tsp_task)
        assert evolved_result is not None

        # Verify database stores complete history
        run_data = system["database"].get_run_summary(run_id)
        assert run_data["task_name"] == "simple_tsp"
        assert run_data["generation_count"] >= 1

    def test_multi_generation_evolution(self, evolution_system):
        """Test evolution across multiple generations."""
        system = evolution_system

        # Set up task
        tsp_task = TSPTask(cities=4)
        system["task_manager"].register_task("multi_gen_tsp", tsp_task)

        # Run multiple generations
        code = "def solve_tsp(cities): return list(range(len(cities)))"
        run_id = system["database"].create_run("multi_generation_test", "multi_gen_tsp")

        for generation in range(3):
            result = system["evaluator"].evaluate_code(code, tsp_task)
            system["database"].store_generation(run_id, generation, [result])

            if generation < 2:  # Don't evolve after last generation
                code = system["evolver"].evolve_code(
                    code, result, tsp_task, generation=generation + 1
                )

        # Verify progression
        run_summary = system["database"].get_run_summary(run_id)
        assert run_summary["generation_count"] == 3

        generations = system["database"].get_generations(run_id)
        assert len(generations) == 3


class TestSystemIntegration:
    """Test integration between major system components."""

    def test_database_evaluator_integration(self, temp_database, sample_task):
        """Test database and evaluator working together."""
        from src.database import Database
        from src.evaluator import Evaluator

        db = Database(temp_database)
        evaluator = Evaluator()

        # Create test code
        code = "def solve(x): return x * 2"

        # Evaluate and store
        result = evaluator.evaluate_code(code, sample_task)
        run_id = db.create_run("integration_test", "test_task")
        db.store_generation(run_id, 0, [result])

        # Retrieve and verify
        stored_generations = db.get_generations(run_id)
        assert len(stored_generations) == 1
        assert stored_generations[0]["fitness"] == result["fitness"]

    def test_llm_evolver_integration(self, mock_llm_provider, sample_task):
        """Test LLM provider and evolver integration."""
        from src.evolve import Evolver

        evolver = Evolver(mock_llm_provider)

        initial_code = "def solve(x): return x"
        initial_result = {"fitness": 0.5, "code": initial_code}

        # Test evolution
        evolved_code = evolver.evolve_code(
            initial_code, initial_result, sample_task, generation=1
        )

        assert evolved_code != initial_code
        assert len(evolved_code) > 0
