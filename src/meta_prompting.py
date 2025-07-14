"""
Meta-prompting module for Cadence evolution system.

This module provides functions for extracting lessons from evolution
history and generating meta-prompts for improved LLM guidance.
"""

import textwrap
from typing import List, Optional, Dict, Any

from .llm import LLMProvider
from .models import LessonHistory


META_PROMPT_TEMPLATE = """
You are analyzing a sequence of attempted improvements to a program designed to solve a complex optimization problem.

Each attempt includes:
- The modified code
- The associated performance cost
- Whether the solution was feasible (1.0) or not (0.0)

Your task is to extract a general lesson statement that could guide the next generation of solutions. This lesson should:
- Identify what strategies were attempted and what didn't work
- Suggest a new direction or adjustment in approach
- Be applicable to the same problem if attempted again

Only output a single lesson statement. Do not explain, summarize, or wrap in markdown.

=== HISTORY ===
{history}

=== END ===

Lesson:
"""


def format_generation_entry(
    entry: Dict[str, Any], feedback: Optional[str] = None
) -> str:
    """
    Format a generation entry for meta-prompting.

    Args:
        entry: Dictionary containing program entry data
        feedback: Optional feedback from previous lesson

    Returns:
        Formatted string representation of the entry
    """
    code = textwrap.indent(entry.get("program_code", "").strip(), "    ")
    fb_line = (
        f"# Feedback from prior lesson: {feedback}"
        if feedback
        else "# Feedback: (none)"
    )
    return f"""## Generation {entry["generation"]}
Cost: {entry["cost"]} | Feasibility: {entry["feasibility"]}
{fb_line}
Code:
{code}
"""


def get_lesson_from_history(
    logs: List[Dict[str, Any]],
    N: Optional[int] = 2,
    previous_lesson: Optional[str] = None,
    llm_provider: Optional[LLMProvider] = None,
) -> Optional[str]:
    """
    Extract a lesson from evolution history using meta-prompting.

    Args:
        logs: List of program evolution entries
        N: Number of recent entries to analyze
        previous_lesson: Previous lesson for context
        llm_provider: LLM provider for lesson generation

    Returns:
        Generated lesson string or None if generation fails
    """
    # Sort and filter recent entries
    recent = sorted(logs, key=lambda x: x["generation"], reverse=True)
    selected = [e for e in recent if "program_code" in e][:N]

    if not selected:
        return None

    # Format history for meta-prompt
    history_entries = []
    for entry in selected:
        formatted_entry = format_generation_entry(entry, previous_lesson)
        history_entries.append(formatted_entry)

    history_text = "\n\n".join(history_entries)
    meta_prompt = META_PROMPT_TEMPLATE.format(history=history_text)

    # Generate lesson using LLM
    if llm_provider is None:
        llm_provider = LLMProvider()

    try:
        lesson = llm_provider.generate_lesson(meta_prompt)
        return lesson.strip() if lesson else None
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate lesson from history: {e}")
        return None


def update_lesson_history(
    lesson_history: LessonHistory, new_lesson: str, generation: int
) -> None:
    """
    Update lesson history with a new lesson.

    Args:
        lesson_history: LessonHistory object to update
        new_lesson: New lesson to add
        generation: Generation when lesson was created
    """
    lesson_history.add_lesson(new_lesson, generation)


def get_recent_lessons_text(lesson_history: LessonHistory, n: int = 3) -> str:
    """
    Get recent lessons formatted as text for prompting.

    Args:
        lesson_history: LessonHistory object
        n: Number of recent lessons to include

    Returns:
        Formatted text of recent lessons
    """
    recent_lessons = lesson_history.get_recent_lessons(n)

    if not recent_lessons:
        return "No previous lessons available."

    formatted_lessons = []
    for lesson, generation in recent_lessons:
        formatted_lessons.append(f"Generation {generation}: {lesson}")

    return "\n".join(formatted_lessons)
