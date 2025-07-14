"""
Abstract base class for optimization tasks.

This module defines the Task interface that all optimization problems
must implement to work with the Cadence evolution system.
"""

from abc import ABC, abstractmethod
from typing import Any
from .models import TaskInstance, EvaluationResult, TaskType


class Task(ABC):
    """
    Abstract base class for defining a problem/task that can be evolved.

    All optimization tasks must inherit from this class and implement
    the required abstract methods.
    """

    @property
    @abstractmethod
    def function_name(self) -> str:
        """
        The name of the function to extract from the evolved code.

        Returns:
            str: Function name (e.g., 'tsp', 'solve', etc.)
        """
        pass

    @property
    def task_type(self) -> TaskType:
        """
        The type of this task. Defaults to CUSTOM for generic tasks.
        Returns:
            TaskType: Task type enum value
        """
        from .models import TaskType

        return TaskType.CUSTOM

    @abstractmethod
    def generate_inputs(self, seed: int) -> Any:
        """
        Generate deterministic input for a given seed.

        Args:
            seed: Random seed for reproducible input generation

        Returns:
            Any: Task-specific input data
        """
        pass

    @abstractmethod
    def evaluate(self, output: Any, input_data: Any) -> EvaluationResult:
        """
        Given a function output and input, return evaluation results.

        Args:
            output: Function output to evaluate
            input_data: Input data used to generate the output

        Returns:
            EvaluationResult: Evaluation results with cost and feasibility
        """
        pass

    @property
    @abstractmethod
    def baseline_program(self) -> str:
        """
        Returns the default, minimal working solution for this task.

        Returns:
            str: Complete code string with START_BLOCK/END_BLOCK markers
        """
        pass

    def is_feasible(self, output: Any, input_data: Any = None, **kwargs: Any) -> bool:
        """
        Check if the output is feasible for the task.

        Args:
            output: Function output to check
            input_data: Input data used to generate the output
            **kwargs: Additional task-specific parameters

        Returns:
            bool: True if output is feasible, False otherwise
        """
        return True

    def create_instance(self, seed: int, **kwargs: Any) -> TaskInstance:
        """
        Create a TaskInstance for this task.

        Args:
            seed: Random seed for instance generation
            **kwargs: Additional parameters for instance creation

        Returns:
            TaskInstance: Configured task instance
        """
        input_data = self.generate_inputs(seed)

        # Convert input data to serializable format
        if hasattr(input_data, "__iter__") and not isinstance(input_data, str):
            data = {"inputs": list(input_data)}
        else:
            data = {"inputs": input_data}

        return TaskInstance(
            id=hash((self.task_type, seed)) % (10**9),  # Simple ID generation
            seed=seed,
            task_type=self.task_type,
            data=data,
        )

    def validate_output_format(self, output: Any) -> bool:
        """
        Validate that output has the expected format for this task.

        Args:
            output: Output to validate

        Returns:
            bool: True if format is valid, False otherwise
        """
        return True
