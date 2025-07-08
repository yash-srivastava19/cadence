"""
Tests for the prompt_sampler module.
"""

from src.prompt_sampler import (
    update_instruction,
    extract_code_blocks,
    build,
    INSTRUCTION_TEMPLATE,
)


class TestPromptSampler:
    """Test prompt sampling functions."""

    def test_update_instruction(self):
        """Test updating global instruction template."""
        original_instruction = INSTRUCTION_TEMPLATE
        new_instruction = "New instruction template"

        update_instruction(new_instruction)

        from src.prompt_sampler import INSTRUCTION_TEMPLATE as updated_template

        assert updated_template == new_instruction

        # Restore original for other tests
        update_instruction(original_instruction)

    def test_extract_code_blocks_single_block(self):
        """Test extracting single code block."""
        code = """
### START_BLOCK
def example():
    x = 1
    return x
### END_BLOCK
"""

        blocks = extract_code_blocks(code)
        assert len(blocks) == 1
        assert "x = 1" in blocks[0]
        assert "return x" in blocks[0]

    def test_extract_code_blocks_multiple_blocks(self):
        """Test extracting multiple code blocks."""
        code = """
### START_BLOCK
def example():
    x = 1
    y = 2
    return x + y
### END_BLOCK

### START_BLOCK

### END_BLOCK
"""

        blocks = extract_code_blocks(code)
        assert len(blocks) == 2
        assert "x = 1" in blocks[0]
        assert "" in blocks[1]
        assert "return x + y" in blocks[0]

    def test_extract_code_blocks_no_blocks(self):
        """Test extracting when no blocks exist."""
        code = """
def example():
    return "no blocks here"
"""

        blocks = extract_code_blocks(code)
        assert blocks == []

    def test_extract_code_blocks_custom_markers(self):
        """Test extracting with custom markers."""
        code = """
<<< START
def example():
    x = 1
<<< END
"""

        blocks = extract_code_blocks(
            code, start_marker="<<< START", end_marker="<<< END"
        )
        assert len(blocks) == 1
        assert "x = 1" in blocks[0]

    def test_build_prompt_with_parent_only(self):
        """Test building prompt with parent program only."""
        parent_program = (
            1,
            0,
            None,
            "def tsp(cities): return list(range(len(cities)))",
            100.0,
            "instance_1",
        )
        inspirations = []

        prompt = build(parent_program, inspirations)

        assert "CURRENT BASELINE SOLUTION" in prompt
        assert "def tsp(cities): return list(range(len(cities)))" in prompt
        assert "Baseline cost: 100.0" in prompt
        assert "PREVIOUS ATTEMPTS" not in prompt

    def test_build_prompt_with_inspirations(self):
        """Test building prompt with inspirations."""
        parent_program = (
            1,
            0,
            None,
            "def tsp(cities): return list(range(len(cities)))",
            100.0,
            "instance_1",
        )
        inspirations = [
            (
                2,
                1,
                1,
                "def tsp(cities): return list(reversed(range(len(cities))))",
                90.0,
                "instance_1",
            ),
            (
                3,
                1,
                1,
                "def tsp(cities): return sorted(range(len(cities)))",
                95.0,
                "instance_1",
            ),
        ]

        prompt = build(parent_program, inspirations)

        assert "CURRENT BASELINE SOLUTION" in prompt
        assert "PREVIOUS ATTEMPTS" in prompt
        assert "Attempt #1 (Cost: 90.0)" in prompt
        assert "Attempt #2 (Cost: 95.0)" in prompt
        assert "list(reversed(range(len(cities))))" in prompt
        assert "sorted(range(len(cities)))" in prompt

    def test_build_prompt_structure(self):
        """Test that built prompt has correct structure."""
        parent_program = (
            1,
            0,
            None,
            "def tsp(cities): return list(range(len(cities)))",
            100.0,
            "instance_1",
        )
        inspirations = []

        prompt = build(parent_program, inspirations)

        # Check for key sections
        assert "You are an expert engineer" in prompt
        assert "efficiency" in prompt
        assert "solution quality" in prompt
        assert "explores a new strategy" in prompt
        assert "### START_BLOCK" in prompt
        assert "### END_BLOCK" in prompt
        assert "INSTRUCTIONS" in prompt
        assert "fundamentally different idea" in prompt
        assert "Output ONLY valid Python code blocks" in prompt

    def test_build_prompt_encourages_novelty(self):
        """Test that prompt encourages novelty and avoids repetition."""
        parent_program = (
            1,
            0,
            None,
            "def tsp(cities): return list(range(len(cities)))",
            100.0,
            "instance_1",
        )
        inspirations = [
            (
                2,
                1,
                1,
                "def tsp(cities): return list(reversed(range(len(cities))))",
                90.0,
                "instance_1",
            ),
        ]

        prompt = build(parent_program, inspirations)

        # Check for novelty-encouraging phrases
        assert "new strategy" in prompt
        assert "not the same as previous attempts" in prompt
        assert "fundamentally different idea" in prompt
        assert "Avoid copying structure" in prompt
        assert "brute-force if possible" in prompt

    def test_build_prompt_mentions_heuristics(self):
        """Test that prompt mentions heuristics and optimization techniques."""
        parent_program = (
            1,
            0,
            None,
            "def tsp(cities): return list(range(len(cities)))",
            100.0,
            "instance_1",
        )
        inspirations = []

        prompt = build(parent_program, inspirations)

        assert "heuristics" in prompt
        assert "local search" in prompt
        assert "rule-based logic" in prompt
        assert "reduces cost" in prompt
        assert "improves reliability" in prompt

    def test_build_prompt_with_complex_parent(self):
        """Test building prompt with complex parent program."""
        parent_program = (
            1,
            0,
            None,
            """
def tsp(cities):
    ### START_BLOCK
    n = len(cities)
    if n <= 1:
        return list(range(n))

    # Simple nearest neighbor heuristic
    tour = [0]
    remaining = set(range(1, n))

    while remaining:
        current = tour[-1]
        next_city = min(remaining, key=lambda c: euclidean_distance(cities[current], cities[c]))
        tour.append(next_city)
        remaining.remove(next_city)

    return tour
    ### END_BLOCK
""",
            85.5,
            "instance_1",
        )
        inspirations = []

        prompt = build(parent_program, inspirations)

        assert "nearest neighbor heuristic" in prompt
        assert "euclidean_distance" in prompt
        assert "Baseline cost: 85.5" in prompt

    def test_build_prompt_formatting(self):
        """Test that prompt is properly formatted."""
        parent_program = (
            1,
            0,
            None,
            "def tsp(cities): return list(range(len(cities)))",
            100.0,
            "instance_1",
        )
        inspirations = []

        prompt = build(parent_program, inspirations)

        # Check that sections are properly delimited
        lines = prompt.split("\n")
        assert any("### CURRENT BASELINE SOLUTION:" in line for line in lines)
        assert any("### INSTRUCTIONS:" in line for line in lines)

        # Check that code is properly indented/formatted
        assert "def tsp(cities): return list(range(len(cities)))" in prompt

    def test_extract_code_blocks_whitespace_handling(self):
        """Test that code block extraction handles whitespace correctly."""
        code = """
### START_BLOCK
def example():

    x = 1
    y = 2

    return x + y

### END_BLOCK
"""

        blocks = extract_code_blocks(code)
        assert len(blocks) == 1

        # Check that leading/trailing whitespace is preserved in the block
        block = blocks[0]
        assert "x = 1" in block
        assert "y = 2" in block
        assert "return x + y" in block
