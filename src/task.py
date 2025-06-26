# src/task.py

from abc import ABC, abstractmethod

class Task(ABC):
    """
    Abstract base class for defining a problem/task that can be evolved.
    """

    @property
    @abstractmethod
    def function_name(self) -> str:
        """
        The name of the function to extract from the evolved code.
        E.g., 'tsp', 'solve', etc.
        """
        pass

    @abstractmethod
    def generate_inputs(self, seed: int):
        """
        Generate deterministic input for a given seed.
        """
        pass

    @abstractmethod
    def evaluate(self, output, input_data) -> float:
        """
        Given a function output and input, return a scalar cost.
        Lower cost = better.
        """
        pass

    @property
    @abstractmethod
    def baseline_program(self) -> str:
        """
        Returns the default, minimal working solution for this task.
        Should be a complete code string with ### START_BLOCK / END_BLOCK markers.
        """
        pass

    def is_feasible(self, output, *args) -> bool:
        """
        Check if the output is feasible for the task.
        This can be overridden by subclasses if needed.
        """
        return True
