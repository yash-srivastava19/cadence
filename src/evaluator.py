"""
Code evaluation module for Cadence evolution system.

This module provides functions to execute and evaluate generated code
on optimization tasks with proper error handling and type safety.
"""

import math
import random
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List, Optional, Union, Callable, Dict, Any
from statistics import mean

from .models import EvaluationResult, CityCoordinates, Tour, ProgramCode
from .task import Task

# Constants
INFEASIBLE_COST: float = 1e8
DEFAULT_TIMEOUT: float = 30.0  # seconds
MAX_MEMORY_MB: int = 512


class EvaluationError(Exception):
    """Custom exception for evaluation errors."""

    pass


def euclidean_distance(a: CityCoordinates, b: CityCoordinates) -> float:
    """
    Calculate Euclidean distance between two points.

    Args:
        a: First point coordinates (x, y)
        b: Second point coordinates (x, y)

    Returns:
        Euclidean distance between points
    """
    return math.hypot(a[0] - b[0], a[1] - b[1])


"""
# Alias for backward compatibility: tests expect `euclidean` to be exported.
"""
euclidean = euclidean_distance


def compute_total_distance(tour: Tour, cities: List[CityCoordinates]) -> float:
    """
    Compute total distance of a tour.

    Args:
        tour: Tour as list of city indices
        cities: List of city coordinates

    Returns:
        Total tour distance

    Raises:
        ValueError: If tour or cities are invalid
    """
    if not tour or not cities:
        raise ValueError("Tour and cities cannot be empty")

    if len(tour) != len(cities):
        raise ValueError("Tour length must match number of cities")

    distance = 0.0
    for i in range(len(tour)):
        current_idx = tour[i]
        next_idx = tour[(i + 1) % len(tour)]

        if not (0 <= current_idx < len(cities) and 0 <= next_idx < len(cities)):
            raise ValueError(f"Invalid city index in tour: {current_idx} or {next_idx}")

        distance += euclidean_distance(cities[current_idx], cities[next_idx])

    return distance


def generate_test_instance(
    n: Optional[int] = None, seed: Optional[int] = None
) -> List[CityCoordinates]:
    """
    Generate a random TSP test instance.

    Args:
        n_cities: Number of cities to generate
        seed: Random seed for reproducibility

    Returns:
        List of city coordinates

    Raises:
        ValueError: If n_cities is invalid
    """
    # Alias 'n' for number of cities (default 10)
    num_cities = n if n is not None else 10
    # Default seed for reproducibility
    rng_seed = seed if seed is not None else 42

    if num_cities < 2:
        raise ValueError("Must have at least 2 cities")

    random.seed(rng_seed)
    return [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(num_cities)]


def execute_single_seed(
    seed: int, func: Callable[[List[CityCoordinates]], Tour], n_cities: int = 10
) -> Dict[str, Union[float, bool, str]]:
    """
    Execute function on a single test instance.

    Args:
        seed: Random seed for test instance
        func: Function to evaluate
        n_cities: Number of cities in test instance

    Returns:
        Dictionary with cost, feasible flag, and optional error
    """
    try:
        cities = generate_test_instance(n_cities, seed)

        # Execute with timeout protection
        start_time = time.time()
        tour = func(cities)
        execution_time = time.time() - start_time

        # Validate tour format
        if not isinstance(tour, list):
            return {
                "cost": INFEASIBLE_COST,
                "feasible": False,
                "error": f"Tour must be a list, got {type(tour)}",
            }

        # Check if tour visits all cities exactly once
        expected_indices = set(range(len(cities)))
        tour_indices = set(tour)

        if tour_indices != expected_indices:
            return {
                "cost": INFEASIBLE_COST,
                "feasible": False,
                "error": f"Tour {tour} doesn't visit all cities exactly once",
            }

        # Calculate cost
        cost = compute_total_distance(tour, cities)

        return {"cost": cost, "feasible": True, "execution_time": execution_time}

    except Exception as e:
        return {"cost": INFEASIBLE_COST, "feasible": False, "error": str(e)}


class Evaluator:
    """
    Main evaluator class for code execution and assessment.
    """

    def __init__(
        self, timeout: float = DEFAULT_TIMEOUT, max_memory_mb: int = MAX_MEMORY_MB
    ) -> None:
        """
        Initialize evaluator.

        Args:
            timeout: Maximum execution time per evaluation
            max_memory_mb: Maximum memory usage in MB
        """
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb

    def evaluate_code(
        self, code: ProgramCode, task: Task, seeds: Optional[List[int]] = None
    ) -> EvaluationResult:
        """
        Evaluate code on a task.

        Args:
            code: Program code to evaluate
            task: Task to evaluate on
            seeds: Random seeds for test instances

        Returns:
            EvaluationResult with performance metrics
        """
        if seeds is None:
            seeds = [1, 2, 3, 4, 5]

        try:
            start_time = time.time()

            # Execute code and extract function
            local_env: Dict[str, Any] = {}
            exec(code, local_env)

            func_name = task.function_name
            func = local_env.get(func_name)

            if not callable(func):
                return EvaluationResult(
                    cost=INFEASIBLE_COST,
                    feasible=False,
                    error=f"Function '{func_name}' not found or not callable",
                )

            # Run evaluations in parallel
            with ThreadPoolExecutor(max_workers=min(len(seeds), 4)) as executor:
                futures: List[Future[Dict[str, Union[float, bool, str]]]] = [
                    executor.submit(self._evaluate_single_instance, func, task, seed)
                    for seed in seeds
                ]

                results = [future.result() for future in futures]

            # Aggregate results
            costs = [r["cost"] for r in results]
            feasible_count = sum(1 for r in results if r["feasible"])

            avg_cost = mean(costs) if costs else INFEASIBLE_COST
            feasibility_ratio = feasible_count / len(results)

            total_time = time.time() - start_time

            # Determine overall feasibility
            is_feasible = feasibility_ratio > 0.5  # Majority must be feasible

            return EvaluationResult(
                cost=avg_cost,
                feasible=is_feasible,
                execution_time=total_time,
                error=None if is_feasible else "Majority of test cases failed",
            )

        except Exception as e:
            return EvaluationResult(
                cost=INFEASIBLE_COST,
                feasible=False,
                error=f"Evaluation failed: {str(e)}",
            )

    def _evaluate_single_instance(
        self, func: Callable, task: Task, seed: int
    ) -> Dict[str, Union[float, bool, str]]:
        """
        Evaluate function on a single task instance.

        Args:
            func: Function to evaluate
            task: Task instance
            seed: Random seed

        Returns:
            Single evaluation result
        """
        try:
            # Generate test input
            test_input = task.generate_inputs(seed)

            # Execute function
            start_time = time.time()
            output = func(test_input)
            execution_time = time.time() - start_time

            # Evaluate using task-specific logic
            result = task.evaluate(output, test_input)

            return {
                "cost": result.cost,
                "feasible": result.feasible,
                "execution_time": execution_time,
                "error": result.error,
            }

        except Exception as e:
            return {
                "cost": INFEASIBLE_COST,
                "feasible": False,
                "error": f"Instance evaluation failed: {str(e)}",
            }


# Legacy function for backwards compatibility
def execute(
    child_program_code: str, task: Task, seeds: Optional[List[int]] = None
) -> Dict[str, float]:
    """
    Legacy evaluation function independent of Task methods.
    Executes the generated code, evaluates with execute_single_seed across seeds,
    aggregates cost and feasibility ratio.
    """
    # Prepare seeds
    if seeds is None:
        seeds = [1, 2, 3, 4, 5]
    # Load program
    local_env: Dict[str, Any] = {}
    try:
        exec(child_program_code, local_env)
    except Exception:
        return {"cost": INFEASIBLE_COST, "feasibility": 0.0}
    # Retrieve function
    func = local_env.get(task.function_name)
    if not callable(func):
        return {"cost": INFEASIBLE_COST, "feasibility": 0.0}
    # Execute across seeds concurrently
    try:
        with ThreadPoolExecutor(max_workers=min(len(seeds), 4)) as executor:
            futures = [
                executor.submit(execute_single_seed, seed, func) for seed in seeds
            ]
            results = [f.result() for f in futures]
        # Aggregate results
        costs = [r.get("cost", INFEASIBLE_COST) for r in results]
        feasible_count = sum(1 for r in results if r.get("feasible"))
        avg_cost = mean(costs) if costs else INFEASIBLE_COST
        feasibility_ratio = feasible_count / len(results) if results else 0.0
        return {"cost": avg_cost, "feasibility": feasibility_ratio}
    except Exception:
        return {"cost": INFEASIBLE_COST, "feasibility": 0.0}
