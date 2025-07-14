"""
Reinforcement Learning agent for Cadence evolution system.

This module provides an RL agent that learns to improve programs
by optimizing reward derived from evaluation metrics.
"""

from typing import List, Tuple, Optional, Any
from ..llm import generate
from ..models import PromptText, ProgramCode
from ..task import Task


class RLAgent:
    """
    A reinforcement learning agent that learns to improve programs
    by optimizing reward derived from evaluator cost.
    """

    def __init__(self, task: Task, model: Optional[Any] = None) -> None:
        """
        Initialize RL agent.

        Args:
            task: Instance of the Task class (used for execution and context)
            model: Optional LLM or policy model for code generation
        """
        self.task: Task = task
        self.model: Optional[Any] = model  # can be LLM or any policy backbone
        self.memory: List[Tuple[str, str, float]] = []  # stores (state, action, reward)
        self.reward_model: Optional[Any] = None

    def sample_action(self, prompt: PromptText, n_samples: int = 4) -> ProgramCode:
        """
        Given a string prompt (state), return a generated action (code).

        Args:
            prompt: Input prompt for code generation
            n_samples: Number of code samples to generate

        Returns:
            Best generated code completion
        """
        # Reuse your LLM logic here
        completions: List[str] = generate(prompt)

        if not completions:
            return ""

        if self.reward_model is not None:
            ranked = self.reward_model.score(prompt, completions)
            best_completion = max(ranked, key=lambda x: x[1])[0]
            return best_completion
        else:
            # Return first completion if no reward model
            return completions[0] if completions else ""

    def observe(self, state: str, action: str, reward: float) -> None:
        """
        Store (state, action, reward) into memory (or policy buffer).

        Args:
            state: Current state representation
            action: Action taken (generated code)
            reward: Reward received for the action
        """
        self.memory.append((state, action, reward))
