"""
Traveling Salesman Problem (TSP) task implementation.

This module implements the TSP optimization problem for the Cadence
evolution system with full type annotations and validation.
"""

import random
from math import sqrt
from typing import List, Optional, Union

from ..task import Task
from ..models import EvaluationResult, TaskType, CityCoordinates, Tour


class TSPTask(Task):
    """
    Traveling Salesman Problem task.

    Generates random city coordinates and evaluates tour quality
    based on total distance traveled.
    """

    def __init__(self, n_cities: Optional[int] = 10) -> None:
        """
        Initialize TSP task.

        Args:
            n_cities: Number of cities in the problem instance
        """
        if n_cities is not None and n_cities < 3:
            raise ValueError("TSP requires at least 3 cities")
        self.n_cities = n_cities or 10

    @property
    def function_name(self) -> str:
        """Function name to extract from evolved code."""
        return "tsp"

    @property
    def task_type(self) -> TaskType:
        """Task type identifier."""
        return TaskType.TSP

    def generate_inputs(self, seed: int) -> List[CityCoordinates]:
        """
        Generate random city coordinates.

        Args:
            seed: Random seed for reproducible generation

        Returns:
            List of (x, y) coordinate tuples
        """
        random.seed(seed)
        return [
            (random.uniform(0, 100), random.uniform(0, 100))
            for _ in range(self.n_cities)
        ]

    def evaluate(
        self, output: Union[List[int], Tour], cities: List[CityCoordinates]
    ) -> EvaluationResult:
        """
        Evaluate a TSP tour.

        Args:
            output: Tour as list of city indices
            cities: List of city coordinates

        Returns:
            EvaluationResult with cost and feasibility
        """
        # Check basic feasibility
        if not self.is_feasible(output, cities):
            return EvaluationResult(
                cost=float("inf"), feasible=False, error="Tour is not feasible"
            )

        # Validate output format
        if not isinstance(output, list) or sorted(output) != list(range(len(cities))):
            return EvaluationResult(
                cost=float("inf"),
                feasible=False,
                error="Tour must visit all cities exactly once",
            )

        # Calculate total distance
        try:
            total_distance = self._calculate_tour_distance(output, cities)
            return EvaluationResult(cost=total_distance, feasible=True)
        except Exception as e:
            return EvaluationResult(
                cost=float("inf"),
                feasible=False,
                error=f"Error calculating tour distance: {str(e)}",
            )

    def _calculate_tour_distance(
        self, tour: Tour, cities: List[CityCoordinates]
    ) -> float:
        """
        Calculate total distance of a tour.

        Args:
            tour: Tour as list of city indices
            cities: List of city coordinates

        Returns:
            Total tour distance
        """

        def distance(i: int, j: int) -> float:
            """Calculate Euclidean distance between two cities."""
            x1, y1 = cities[i]
            x2, y2 = cities[j]
            return sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

        total = 0.0
        for i in range(len(tour)):
            current_city = tour[i]
            next_city = tour[(i + 1) % len(tour)]
            total += distance(current_city, next_city)

        return total

    def is_feasible(
        self, output: Union[List[int], Tour], cities: List[CityCoordinates]
    ) -> bool:
        """
        Check if tour is feasible.

        Args:
            output: Tour to check
            cities: List of city coordinates

        Returns:
            True if tour is feasible, False otherwise
        """
        if not isinstance(output, list):
            return False

        if len(output) != len(cities):
            return False

        # Check that all city indices are present exactly once
        if sorted(output) != list(range(len(cities))):
            return False

        # Check for valid city indices
        if any(
            not isinstance(idx, int) or idx < 0 or idx >= len(cities) for idx in output
        ):
            return False

        return True

    def validate_output_format(self, output: Union[List[int], Tour]) -> bool:
        """
        Validate output format for TSP.

        Args:
            output: Output to validate

        Returns:
            True if format is valid
        """
        return (
            isinstance(output, list)
            and all(isinstance(x, int) for x in output)
            and len(output) == self.n_cities
        )

    @property
    def baseline_program(self) -> str:
        """
        Baseline TSP solution (identity permutation).

        Returns:
            Complete program with START/END block markers
        """
        return """### START_BLOCK
def tsp(cities):
    '''Simple baseline: visit cities in order 0, 1, 2, ...'''
    return list(range(len(cities)))
### END_BLOCK"""

    def get_optimal_tour_length(self, cities: List[CityCoordinates]) -> Optional[float]:
        """
        Get optimal tour length if known (for small instances).

        Args:
            cities: List of city coordinates

        Returns:
            Optimal tour length if computable, None otherwise
        """
        # For very small instances, we could compute optimal
        # For now, return None (optimal unknown)
        if len(cities) <= 4:
            # Could implement brute force for tiny instances
            pass
        return None

    def __repr__(self) -> str:
        """String representation of TSP task."""
        return f"TSPTask(n_cities={self.n_cities})"
