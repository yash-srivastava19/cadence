"""
Tests for the evaluator module.
"""

from unittest.mock import patch, MagicMock

from src.evaluator import (
    euclidean,
    compute_total_distance,
    generate_test_instance,
    execute_single_seed,
    execute,
    INFEASIBLE_COST,
)


class TestEvaluator:
    """Test evaluation functions."""

    def test_euclidean_distance(self):
        """Test euclidean distance calculation."""
        # Test simple cases
        assert euclidean((0, 0), (3, 4)) == 5.0
        assert euclidean((0, 0), (0, 0)) == 0.0
        assert euclidean((1, 1), (1, 1)) == 0.0

        # Test negative coordinates
        assert euclidean((-1, -1), (2, 3)) == 5.0

    def test_compute_total_distance(self):
        """Test total distance computation."""
        cities = [(0, 0), (1, 0), (1, 1), (0, 1)]

        # Test simple square tour
        tour = [0, 1, 2, 3]
        distance = compute_total_distance(tour, cities)
        assert distance == 4.0  # 1 + 1 + 1 + 1

        # Test different tour order
        tour = [0, 2, 1, 3]
        distance = compute_total_distance(tour, cities)
        expected = (
            euclidean((0, 0), (1, 1))
            + euclidean((1, 1), (1, 0))
            + euclidean((1, 0), (0, 1))
            + euclidean((0, 1), (0, 0))
        )
        assert abs(distance - expected) < 1e-10

    def test_generate_test_instance(self):
        """Test test instance generation."""
        # Test deterministic generation
        cities1 = generate_test_instance(n=5, seed=42)
        cities2 = generate_test_instance(n=5, seed=42)
        assert cities1 == cities2

        # Test different seeds produce different results
        cities3 = generate_test_instance(n=5, seed=43)
        assert cities1 != cities3

        # Test correct number of cities
        cities = generate_test_instance(n=10, seed=1)
        assert len(cities) == 10

        # Test coordinates are within bounds
        for x, y in cities:
            assert 0 <= x <= 100
            assert 0 <= y <= 100

    def test_execute_single_seed_valid(self):
        """Test single seed execution with valid function."""

        def valid_tsp(cities):
            return list(range(len(cities)))

        result = execute_single_seed(42, valid_tsp)
        assert result["feasible"] is True
        assert result["cost"] > 0
        assert result["cost"] < INFEASIBLE_COST

    def test_execute_single_seed_invalid_tour(self):
        """Test single seed execution with invalid tour."""

        def invalid_tsp(cities):
            return [0, 1]  # Missing cities

        result = execute_single_seed(42, invalid_tsp)
        assert result["feasible"] is False
        assert result["cost"] == INFEASIBLE_COST

    def test_execute_single_seed_exception(self):
        """Test single seed execution with exception."""

        def error_tsp(cities):
            raise ValueError("Test error")

        result = execute_single_seed(42, error_tsp)
        assert result["feasible"] is False
        assert result["cost"] == INFEASIBLE_COST

    def test_execute_valid_program(self):
        """Test execution of valid program."""
        program_code = """
def tsp(cities):
    return list(range(len(cities)))
"""

        # Mock task
        task = MagicMock()
        task.function_name = "tsp"

        result = execute(program_code, task, seeds=[1, 2, 3])
        assert result["feasibility"] > 0
        assert result["cost"] < INFEASIBLE_COST

    def test_execute_invalid_program(self):
        """Test execution of invalid program."""
        program_code = """
def invalid_function(cities):
    return "not a list"
"""

        # Mock task
        task = MagicMock()
        task.function_name = "tsp"

        result = execute(program_code, task, seeds=[1, 2, 3])
        assert result["feasibility"] == 0.0
        assert result["cost"] == INFEASIBLE_COST

    def test_execute_missing_function(self):
        """Test execution with missing function."""
        program_code = """
def wrong_name(cities):
    return list(range(len(cities)))
"""

        # Mock task
        task = MagicMock()
        task.function_name = "tsp"

        result = execute(program_code, task, seeds=[1, 2, 3])
        assert result["feasibility"] == 0.0
        assert result["cost"] == INFEASIBLE_COST

    def test_execute_syntax_error(self):
        """Test execution with syntax error."""
        program_code = """
def tsp(cities):
    return list(range(len(cities))  # Missing closing parenthesis
"""

        # Mock task
        task = MagicMock()
        task.function_name = "tsp"

        result = execute(program_code, task, seeds=[1, 2, 3])
        assert result["feasibility"] == 0.0
        assert result["cost"] == INFEASIBLE_COST

    @patch("src.evaluator.ThreadPoolExecutor")
    def test_execute_concurrent_execution(self, mock_executor):
        """Test concurrent execution with ThreadPoolExecutor."""
        # Mock executor and futures
        mock_future = MagicMock()
        mock_future.result.return_value = {"cost": 100.0, "feasible": True}

        mock_executor_instance = MagicMock()
        mock_executor_instance.submit.return_value = mock_future
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.__exit__.return_value = None
        mock_executor.return_value = mock_executor_instance

        program_code = """
def tsp(cities):
    return list(range(len(cities)))
"""

        # Mock task
        task = MagicMock()
        task.function_name = "tsp"

        result = execute(program_code, task, seeds=[1, 2, 3])

        # Verify executor was used
        assert mock_executor.called
        assert mock_executor_instance.submit.call_count == 3
        assert result["cost"] == 100.0
        assert result["feasibility"] == 1.0
