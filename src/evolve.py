"""
Code evolution and diff application module.

This module provides functions to apply code modifications using
START/END block markers with comprehensive type safety.
"""

import re
from typing import List, Optional, Iterator

from .models import ProgramCode, CodeBlock


class EvolutionError(Exception):
    """Custom exception for evolution operations."""

    pass


def apply_diff(parent_program: ProgramCode, diffs: List[str]) -> ProgramCode:
    """
    Apply list of diff code blocks into parent_program using START/END markers.

    Args:
        parent_program: Original program code
        diffs: List of code diffs to apply

    Returns:
        Modified child program code

    Raises:
        EvolutionError: If diff application fails
    """
    if not isinstance(parent_program, str):
        raise EvolutionError("Parent program must be a string")

    if not isinstance(diffs, list):
        raise EvolutionError("Diffs must be a list")

    try:
        return _apply_diff_in_strs(parent_program, diffs)
    except Exception as e:
        raise EvolutionError(f"Failed to apply diff: {e}")


def _apply_diff_in_strs(
    file_str: ProgramCode,
    diffs: List[str],
    start_marker: Optional[str] = "### START_BLOCK",
    end_marker: Optional[str] = "### END_BLOCK",
) -> ProgramCode:
    """
    Replace code blocks in file_str marked by custom start and end markers.
    Each diff replaces one marked block in order.

    Args:
        file_str: Source code string
        diffs: List of replacement code blocks
        start_marker: Start block marker
        end_marker: End block marker

    Returns:
        Modified code string with diffs applied

    Raises:
        EvolutionError: If markers are invalid or diff application fails
    """
    if not start_marker or not end_marker:
        raise EvolutionError("Start and end markers cannot be empty")

    if start_marker == end_marker:
        raise EvolutionError("Start and end markers must be different")

    try:
        # Create regex pattern to find blocks
        pattern = re.compile(
            rf"{re.escape(start_marker)}[\s\S]*?{re.escape(end_marker)}", re.MULTILINE
        )

        # Create iterator over diffs
        diff_iter: Iterator[str] = iter(diffs)

        def replacer(match: re.Match[str]) -> str:
            """Replace function for regex substitution."""
            try:
                replacement = next(diff_iter)
                # Ensure replacement is properly formatted
                cleaned_replacement = replacement.strip()
                return f"{start_marker}\n{cleaned_replacement}\n{end_marker}"
            except StopIteration:
                # No more diffs available, leave block unchanged
                return match.group(0)

        # Apply replacements
        result = pattern.sub(replacer, file_str)

        # Validate result
        if not result:
            raise EvolutionError("Diff application resulted in empty code")

        return result

    except re.error as e:
        raise EvolutionError(f"Regex error in diff application: {e}")
    except Exception as e:
        raise EvolutionError(f"Unexpected error in diff application: {e}")


def extract_blocks(
    code: ProgramCode,
    start_marker: str = "### START_BLOCK",
    end_marker: str = "### END_BLOCK",
) -> List[CodeBlock]:
    """
    Extract all code blocks from a program.

    Args:
        code: Source code to extract from
        start_marker: Start block marker
        end_marker: End block marker

    Returns:
        List of CodeBlock objects
    """
    try:
        pattern = rf"{re.escape(start_marker)}\n(.*?)\n{re.escape(end_marker)}"
        matches = re.findall(pattern, code, re.DOTALL)

        blocks = []
        for i, match in enumerate(matches):
            blocks.append(CodeBlock(content=match.strip(), language="python"))

        return blocks

    except Exception as e:
        raise EvolutionError(f"Failed to extract blocks: {e}")


def count_blocks(
    code: ProgramCode,
    start_marker: str = "### START_BLOCK",
    end_marker: str = "### END_BLOCK",
) -> int:
    """
    Count the number of blocks in code.

    Args:
        code: Source code to analyze
        start_marker: Start block marker
        end_marker: End block marker

    Returns:
        Number of blocks found
    """
    try:
        pattern = rf"{re.escape(start_marker)}[\s\S]*?{re.escape(end_marker)}"
        matches = re.findall(pattern, code, re.MULTILINE)
        return len(matches)
    except Exception:
        return 0


def validate_block_structure(
    code: ProgramCode,
    start_marker: str = "### START_BLOCK",
    end_marker: str = "### END_BLOCK",
) -> bool:
    """
    Validate that code has properly matched start/end markers.

    Args:
        code: Source code to validate
        start_marker: Start block marker
        end_marker: End block marker

    Returns:
        True if structure is valid, False otherwise
    """
    try:
        start_count = code.count(start_marker)
        end_count = code.count(end_marker)

        # Must have equal numbers of start and end markers
        if start_count != end_count:
            return False

        # Check that markers are properly nested
        # Simple check: ensure no overlapping blocks
        pattern = rf"{re.escape(start_marker)}[\s\S]*?{re.escape(end_marker)}"
        matches = re.findall(pattern, code, re.MULTILINE)

        # Count of regex matches should equal start_count
        return len(matches) == start_count

    except Exception:
        return False


def apply_single_diff(
    parent_program: ProgramCode,
    diff: str,
    block_index: int = 0,
    start_marker: str = "### START_BLOCK",
    end_marker: str = "### END_BLOCK",
) -> ProgramCode:
    """
    Apply a single diff to a specific block.

    Args:
        parent_program: Original program code
        diff: Single diff to apply
        block_index: Index of block to replace (0-based)
        start_marker: Start block marker
        end_marker: End block marker

    Returns:
        Modified program code

    Raises:
        EvolutionError: If block index is invalid or diff fails
    """
    blocks = extract_blocks(parent_program, start_marker, end_marker)

    if block_index >= len(blocks):
        raise EvolutionError(
            f"Block index {block_index} out of range (0-{len(blocks) - 1})"
        )

    # Create diff list with None for blocks we don't want to change
    diffs = []
    for i in range(len(blocks)):
        if i == block_index:
            diffs.append(diff)

    # Apply only the single diff
    return apply_diff(parent_program, diffs[:1])
