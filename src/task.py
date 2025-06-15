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
