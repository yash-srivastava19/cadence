"""
Tests for the LLM module.
"""

from types import SimpleNamespace
from unittest.mock import patch
import os

from src.llm import mutate_instruction, generate, extract_valid_blocks


def _api_response(text: str) -> SimpleNamespace:
    """A stand-in for the google-genai response object.

    Not a MagicMock: `_make_request` passes `prompt_token_count` and friends to
    the typed `LLMResponse`, and auto-created Mock attributes fail validation.
    """
    return SimpleNamespace(
        text=text,
        prompt_token_count=None,
        candidates_token_count=None,
        finish_reason=None,
    )


class TestLLM:
    """Test LLM functions."""

    @patch("src.llm.client")
    def test_mutate_instruction_success(self, mock_client):
        """Test successful instruction mutation."""
        # Mock successful response
        mock_client.models.generate_content.return_value = _api_response(
            "Improved instruction text"
        )

        base_instruction = "Original instruction"
        result = mutate_instruction(base_instruction)

        assert result == "Improved instruction text"
        mock_client.models.generate_content.assert_called_once()

        # Verify the call contains the base instruction
        call_args = mock_client.models.generate_content.call_args
        assert base_instruction in call_args[1]["contents"]

    @patch("src.llm.client")
    def test_mutate_instruction_failure(self, mock_client):
        """Test instruction mutation with API failure."""
        # Mock API failure
        mock_client.models.generate_content.side_effect = Exception("API Error")

        base_instruction = "Original instruction"
        result = mutate_instruction(base_instruction)

        # Should return original instruction on failure
        assert result == base_instruction

    @patch("src.llm.client")
    def test_generate_success(self, mock_client):
        """Test successful code generation."""
        # Mock successful response with code blocks
        mock_client.models.generate_content.return_value = _api_response(
            """
Here's the improved code:

### START_BLOCK
def improved_function():
    return "better code"
### END_BLOCK

And another block:

### START_BLOCK
def another_function():
    return "more code"
### END_BLOCK
"""
        )

        prompt = "Improve this code"
        result = generate(prompt)

        assert len(result) == 2
        assert "def improved_function():" in result[0]
        assert "def another_function():" in result[1]
        assert 'return "better code"' in result[0]
        assert 'return "more code"' in result[1]

    @patch("src.llm.client")
    def test_generate_failure(self, mock_client):
        """Test code generation with API failure."""
        # Mock API failure
        mock_client.models.generate_content.side_effect = Exception("API Error")

        prompt = "Improve this code"
        result = generate(prompt)

        # Should return empty list on failure
        assert result == []

    @patch("src.llm.client")
    def test_generate_no_blocks(self, mock_client):
        """Test generation with no valid blocks."""
        # Mock response with no code blocks
        mock_client.models.generate_content.return_value = _api_response(
            "Here's some text but no code blocks"
        )

        prompt = "Improve this code"
        result = generate(prompt)

        assert result == []

    def test_extract_valid_blocks_single_block(self):
        """Test extracting single code block."""
        text = """
Some text here.

### START_BLOCK
def test():
    return "hello"
### END_BLOCK

More text here.
"""

        blocks = extract_valid_blocks(text)
        assert len(blocks) == 1
        assert "def test():" in blocks[0]
        assert 'return "hello"' in blocks[0]

    def test_extract_valid_blocks_multiple_blocks(self):
        """Test extracting multiple code blocks."""
        text = """
### START_BLOCK
def func1():
    return 1
### END_BLOCK

Some explanation text.

### START_BLOCK
def func2():
    return 2
### END_BLOCK
"""

        blocks = extract_valid_blocks(text)
        assert len(blocks) == 2
        assert "def func1():" in blocks[0]
        assert "def func2():" in blocks[1]
        assert "return 1" in blocks[0]
        assert "return 2" in blocks[1]

    def test_extract_valid_blocks_no_blocks(self):
        """Test extracting when no blocks exist."""
        text = "This text has no code blocks in it."

        blocks = extract_valid_blocks(text)
        assert blocks == []

    def test_extract_valid_blocks_malformed_blocks(self):
        """Test extracting with malformed blocks."""
        text = """
### START_BLOCK
def incomplete_block():
    return "missing end"

### END_BLOCK
def complete_block():
    return "complete"
### END_BLOCK
"""

        blocks = extract_valid_blocks(text)
        # Should only extract the properly formed block
        assert len(blocks) == 1
        assert "def incomplete_block():" in blocks[0]

    def test_extract_valid_blocks_nested_markers(self):
        """Test extracting blocks with nested content."""
        text = """
### START_BLOCK
def outer_function():
    # This comment has ### START_BLOCK in it
    code = "### END_BLOCK"
    return code
### END_BLOCK
"""

        blocks = extract_valid_blocks(text)
        assert len(blocks) == 1
        assert "def outer_function():" in blocks[0]
        assert "# This comment has ### START_BLOCK in it" in blocks[0]
        assert 'code = "### END_BLOCK"' in blocks[0]

    def test_extract_valid_blocks_multiline_complex(self):
        """Test extracting complex multiline blocks."""
        text = """
### START_BLOCK
def complex_function(cities):
    n = len(cities)
    best_tour = None
    best_distance = float('inf')

    # Try different starting points
    for start in range(n):
        tour = [start]
        remaining = set(range(n)) - {start}

        while remaining:
            current = tour[-1]
            next_city = min(remaining,
                          key=lambda c: euclidean_distance(cities[current], cities[c]))
            tour.append(next_city)
            remaining.remove(next_city)

        distance = calculate_tour_distance(tour, cities)
        if distance < best_distance:
            best_distance = distance
            best_tour = tour

    return best_tour
### END_BLOCK
"""

        blocks = extract_valid_blocks(text)
        assert len(blocks) == 1
        assert "def complex_function(cities):" in blocks[0]
        assert "best_tour = None" in blocks[0]
        assert "for start in range(n):" in blocks[0]
        assert "return best_tour" in blocks[0]

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    @patch("src.llm.genai.Client")
    def test_client_initialization(self, mock_genai_client):
        """The client is built on first use, not at import."""
        import importlib

        import src.llm

        importlib.reload(src.llm)
        mock_genai_client.assert_not_called()

        src.llm._provider()
        mock_genai_client.assert_called_with(api_key="test_key")

    def test_extract_valid_blocks_empty_blocks(self):
        """Test extracting empty blocks."""
        text = """
### START_BLOCK

### END_BLOCK

### START_BLOCK


### END_BLOCK
"""

        blocks = extract_valid_blocks(text)
        assert len(blocks) == 2
        assert blocks[0].strip() == ""
        assert blocks[1].strip() == ""
