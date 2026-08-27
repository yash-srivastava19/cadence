"""Mock responses for LLM interactions during testing."""


class MockLLMResponse:
    """Mock LLM response for testing."""

    def __init__(self, text):
        self.text = text


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self):
        self.call_count = 0
        self.last_prompt = None
        self.responses = []
        self.should_fail = False

    def set_responses(self, responses):
        """Set predetermined responses."""
        self.responses = responses

    def set_should_fail(self, should_fail=True):
        """Configure whether to simulate failures."""
        self.should_fail = should_fail

    def generate_content(self, prompt):
        """Mock generate_content method."""
        self.call_count += 1
        self.last_prompt = prompt

        if self.should_fail:
            raise Exception("Mock LLM failure")

        if not self.responses:
            # Default response
            return MockLLMResponse("return list(range(len(cities)))")

        # Cycle through responses
        response_idx = (self.call_count - 1) % len(self.responses)
        return MockLLMResponse(self.responses[response_idx])


# Common mock responses
MOCK_RESPONSES = {
    "simple_improvement": """### START_BLOCK
def tsp(cities):
    # Simple nearest neighbor
    n = len(cities)
    if n <= 1:
        return list(range(n))

    tour = [0]
    unvisited = set(range(1, n))
    current = 0

    while unvisited:
        nearest = min(unvisited, key=lambda city:
            ((cities[current][0] - cities[city][0])**2 +
             (cities[current][1] - cities[city][1])**2)**0.5)
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return tour
### END_BLOCK""",
    "invalid_code": """### START_BLOCK
def tsp(cities):
    return [0, 1]  # Invalid - missing cities
### END_BLOCK""",
    "syntax_error": """### START_BLOCK
def tsp(cities):
    return [i for i in range(len(cities)  # Syntax error
### END_BLOCK""",
    "no_blocks": "This response has no code blocks.",
    "multiple_blocks": """### START_BLOCK
def tsp(cities):
    return list(range(len(cities)))
### END_BLOCK

### START_BLOCK
def another_function():
    pass
### END_BLOCK""",
    "meta_prompt": (
        "Focus on implementing greedy nearest-neighbor algorithms"
        " for better TSP solutions."
    ),
}
