import re

def apply_diff(parent_program: str, diffs: list[str]) -> str:
    """
    Apply list of diff code blocks into parent_program using START/END markers.

    Returns:
        str: Modified child program.
    """
    return _apply_diff_in_strs(parent_program, diffs)


def _apply_diff_in_strs(file_str: str, diffs: list[str],
                        start_marker="### START_BLOCK",
                        end_marker="### END_BLOCK") -> str:
    """
    Replace code blocks in file_str marked by custom start and end markers.
    Each diff replaces one marked block in order.
    """
    pattern = re.compile(
        rf"{re.escape(start_marker)}[\s\S]*?{re.escape(end_marker)}", re.MULTILINE
    )
    diff_iter = iter(diffs)

    def replacer(match):
        try:
            replacement = next(diff_iter)
            return f"{start_marker}\n{replacement.strip()}\n{end_marker}"
        except StopIteration:
            return match.group(0)  # No more diffs, leave unchanged

    return pattern.sub(replacer, file_str)
