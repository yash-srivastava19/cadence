"""
Tests for the evolve module.
"""

from src.evolve import apply_diff, _apply_diff_in_strs


class TestEvolve:
    """Test evolution functions."""

    def test_apply_diff_single_block(self):
        """Test applying diff to single block."""
        parent_program = """
def example():
    ### START_BLOCK
    return "old code"
    ### END_BLOCK
"""

        diffs = ['return "new code"']
        result = apply_diff(parent_program, diffs)

        expected = """
def example():
    ### START_BLOCK
    return "new code"
    ### END_BLOCK
"""
        result_lines = [
            line.strip() for line in result.strip().split("\n") if line.strip()
        ]
        expected_lines = [
            line.strip() for line in expected.strip().split("\n") if line.strip()
        ]
        assert result_lines == expected_lines

    def test_apply_diff_multiple_blocks(self):
        """Test applying diff to multiple blocks."""
        parent_program = """
def example():
    ### START_BLOCK
    x = 1
    ### END_BLOCK

    ### START_BLOCK
    y = 2
    ### END_BLOCK
    return x + y
"""

        diffs = ["x = 10", "y = 20"]
        result = apply_diff(parent_program, diffs)

        expected = """
def example():
    ### START_BLOCK
    x = 10
    ### END_BLOCK

    ### START_BLOCK
    y = 20
    ### END_BLOCK
    return x + y
"""
        result_lines = [
            line.strip() for line in result.strip().split("\n") if line.strip()
        ]
        expected_lines = [
            line.strip() for line in expected.strip().split("\n") if line.strip()
        ]
        assert result_lines == expected_lines

    def test_apply_diff_fewer_diffs_than_blocks(self):
        """Test applying fewer diffs than blocks."""
        parent_program = """
def example():
    ### START_BLOCK
    x = 1
    ### END_BLOCK

    ### START_BLOCK
    y = 2
    ### END_BLOCK
    return x + y
"""

        diffs = ["x = 10"]  # Only one diff for two blocks
        result = apply_diff(parent_program, diffs)

        expected = """
def example():
    ### START_BLOCK
    x = 10
    ### END_BLOCK

    ### START_BLOCK
    y = 2
    ### END_BLOCK
    return x + y
"""
        result_lines = [
            line.strip() for line in result.strip().split("\n") if line.strip()
        ]
        expected_lines = [
            line.strip() for line in expected.strip().split("\n") if line.strip()
        ]
        assert result_lines == expected_lines

    def test_apply_diff_no_blocks(self):
        """Test applying diff when no blocks exist."""
        parent_program = """
def example():
    return "no blocks here"
"""

        diffs = ["x = 10"]
        result = apply_diff(parent_program, diffs)

        # Should return original program unchanged
        result_lines = [
            line.strip() for line in result.strip().split("\n") if line.strip()
        ]
        parent_lines = [
            line.strip() for line in parent_program.strip().split("\n") if line.strip()
        ]
        assert result_lines == parent_lines

    def test_apply_diff_empty_diffs(self):
        """Test applying empty diffs."""
        parent_program = """
def example():
    ### START_BLOCK
    x = 1
    ### END_BLOCK
"""

        diffs = []
        result = apply_diff(parent_program, diffs)

        # Should return original program unchanged
        result_lines = [
            line.strip() for line in result.strip().split("\n") if line.strip()
        ]
        parent_lines = [
            line.strip() for line in parent_program.strip().split("\n") if line.strip()
        ]
        assert result_lines == parent_lines

    def test_apply_diff_multiline_blocks(self):
        """Test applying diff to multiline blocks."""
        parent_program = """
def tsp(cities):
    ### START_BLOCK
    n = len(cities)
    tour = list(range(n))
    return tour
    ### END_BLOCK
"""

        diffs = [
            """
    n = len(cities)
    best_tour = None
    best_distance = float('inf')

    for i in range(n):
        tour = list(range(i, n)) + list(range(i))
        if len(tour) < best_distance:
            best_tour = tour

    return best_tour or list(range(n))
"""
        ]

        result = apply_diff(parent_program, diffs)

        assert "best_tour = None" in result
        assert "best_distance = float('inf')" in result
        assert "for i in range(n):" in result

    def test_apply_diff_in_strs_custom_markers(self):
        """Test applying diff with custom markers."""
        parent_program = """
def example():
    <<< START
    x = 1
    <<< END
"""

        diffs = ["x = 10"]
        result = _apply_diff_in_strs(
            parent_program, diffs, start_marker="<<< START", end_marker="<<< END"
        )

        expected = """
def example():
    <<< START
    x = 10
    <<< END
"""
        result_lines = [
            line.strip() for line in result.strip().split("\n") if line.strip()
        ]
        expected_lines = [
            line.strip() for line in expected.strip().split("\n") if line.strip()
        ]
        assert result_lines == expected_lines

    def test_apply_diff_preserves_indentation(self):
        """Test that diff application preserves block structure."""
        parent_program = """
class Example:
    def method(self):
        ### START_BLOCK
        if True:
            return "old"
        ### END_BLOCK
"""

        diffs = ['if True:\n            return "new"']
        result = apply_diff(parent_program, diffs)

        assert "### START_BLOCK" in result
        assert "### END_BLOCK" in result
        assert 'return "new"' in result

    def test_apply_diff_complex_regex_content(self):
        """Test applying diff with regex-special characters."""
        parent_program = """
def example():
    ### START_BLOCK
    pattern = r".*\d+.*"
    return re.match(pattern, "test123")
    ### END_BLOCK
"""

        diffs = ['pattern = r".*\\w+.*"\nreturn re.match(pattern, "test")']
        result = apply_diff(parent_program, diffs)

        assert ".*\\w+.*" in result
        assert 're.match(pattern, "test")' in result
