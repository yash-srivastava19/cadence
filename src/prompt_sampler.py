"""
Prompt building and code extraction module for Cadence evolution system.

This module provides typed functions for building prompts and extracting
code blocks with proper validation and error handling.
"""

import re
from typing import List, Optional, Dict, Any

from .models import ProgramCode, PromptText


class PromptError(Exception):
    """Custom exception for prompt operations."""

    pass


# Global mutable instruction template
INSTRUCTION_TEMPLATE: str = """
Your task is to modify this program to reduce the cost and increase efficiency.
Only modify code inside the START_BLOCK and END_BLOCK markers.
Do not repeat the same logic unless necessary.
Avoid markdown or explanation in your output.
Ensure the code is self-contained and executable.
"""


def update_instruction(new_instruction: str) -> None:
    """
    Updates the global instruction template used in prompts.

    Args:
        new_instruction: New instruction template to use

    Raises:
        PromptError: If instruction is invalid
    """
    global INSTRUCTION_TEMPLATE

    if not isinstance(new_instruction, str):
        raise PromptError("Instruction must be a string")

    if not new_instruction.strip():
        raise PromptError("Instruction cannot be empty")

    INSTRUCTION_TEMPLATE = new_instruction.strip()


def extract_code_blocks(
    code: ProgramCode,
    start_marker: str = "### START_BLOCK",
    end_marker: str = "### END_BLOCK",
) -> List[str]:
    """
    Extract code blocks that are between start and end markers.

    Args:
        code: Source code to extract from
        start_marker: Start block marker
        end_marker: End block marker

    Returns:
        List of extracted code blocks

    Raises:
        PromptError: If extraction fails
    """
    if not isinstance(code, str):
        raise PromptError("Code must be a string")

    if not start_marker or not end_marker:
        raise PromptError("Markers cannot be empty")

    try:
        pattern = re.compile(
            rf"{re.escape(start_marker)}\n([\s\S]*?)\n{re.escape(end_marker)}",
            re.MULTILINE,
        )
        return [match.group(1).strip() for match in pattern.finditer(code)]
    except re.error as e:
        raise PromptError(f"Invalid regex pattern: {e}")


def build(
    parent_program: Dict[str, Any],
    inspirations: List[str],
    lesson: Optional[str] = None,
) -> PromptText:
    """
    Builds a structured prompt to encourage novelty and heuristics.

    Args:
        parent_program: Dictionary containing parent program information
        inspirations: List of inspiration examples
        lesson: Optional lesson from previous iterations

    Returns:
        Formatted prompt text for LLM

    Raises:
        PromptError: If prompt building fails
    """
    # Parent program can be a dict or tuple/list with structured fields
    if not isinstance(parent_program, (dict, list, tuple)):
        raise PromptError("Parent program must be a dictionary or tuple/list")

    if not isinstance(inspirations, list):
        raise PromptError("Inspirations must be a list")

    # Extract code and cost from parent_program
    try:
        if isinstance(parent_program, (list, tuple)):
            # For runtime tuples: (id, parent_id, instance_id, code, cost, ...)
            # Or test tuples: (id, parent_id, None, code, cost, ...)
            code = parent_program[3]
            cost = parent_program[4]
        else:
            code = parent_program.get("code")
            cost = parent_program.get("cost")
    except (IndexError, KeyError, TypeError):
        raise PromptError("Parent program must contain code and cost information")

    if not code:
        raise PromptError("Parent program code cannot be empty")

    try:
        prompt = """You are an expert engineer tasked with improving a Python program that solves a real-world optimization problem.

The current implementation may be functional, but there is significant room for improvement in:
- efficiency
- solution quality
- clarity and generalization

Your task is to generate a modified version of the code that:
- explores a new strategy (not the same as previous attempts)
- avoids brute-force if possible
- uses simple heuristics, local search, or rule-based logic
- reduces cost and improves reliability over multiple test cases

Only change code inside the blocks marked by:
    ### START_BLOCK
    ...code...
    ### END_BLOCK

You MUST output the same number of blocks as in the parent program. Do NOT include anything else.
"""

        if lesson and isinstance(lesson, str) and lesson.strip():
            prompt += f"### GUIDING LESSON:\n{lesson.strip()}\n\n"

        # Add the current (parent) baseline
        prompt += "\n### CURRENT BASELINE SOLUTION:\n"
        prompt += str(code) + "\n"
        prompt += f"# Baseline cost: {cost}\n"

        # Add inspiration programs if any
        if inspirations:
            prompt += "\n### PREVIOUS ATTEMPTS:\n"
            for i, insp in enumerate(inspirations):
                # insp tuple/list: (id, parent_id, [instance_id,] code, cost, ...)
                insp_code = insp[3]
                insp_cost = insp[4]
                prompt += f"\n## Attempt #{i + 1} (Cost: {insp_cost})\n"
                prompt += str(insp_code) + "\n"

        # Final reminder
        prompt += "\n### INSTRUCTIONS:\n"
        prompt += "- Try a fundamentally different idea from previous versions.\n"
        prompt += "- Avoid copying structure unless necessary.\n"
        prompt += "- Do not include extra explanation or comments.\n"
        prompt += "- Output ONLY valid Python code blocks between the markers.\n"

        return prompt

    except Exception as e:
        raise PromptError(f"Failed to build prompt: {e}")
