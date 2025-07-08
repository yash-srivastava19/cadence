"""Sample code fixtures for testing."""

# Sample TSP implementations for testing
SAMPLE_TSP_BASELINE = """### START_BLOCK
def tsp(cities):
    return list(range(len(cities)))
### END_BLOCK"""

SAMPLE_TSP_IMPROVED = """### START_BLOCK
def tsp(cities):
    n = len(cities)
    if n <= 3:
        return list(range(n))

    # Nearest neighbor heuristic
    unvisited = set(range(1, n))
    tour = [0]
    current = 0

    while unvisited:
        nearest = min(unvisited, key=lambda city:
            ((cities[current][0] - cities[city][0])**2 +
             (cities[current][1] - cities[city][1])**2)**0.5)
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return tour
### END_BLOCK"""

SAMPLE_TSP_INVALID = """### START_BLOCK
def tsp(cities):
    return [0, 1]  # Invalid: doesn't visit all cities
### END_BLOCK"""

SAMPLE_TSP_SYNTAX_ERROR = """### START_BLOCK
def tsp(cities):
    return [i for i in range(len(cities)  # Missing closing bracket
### END_BLOCK"""

# Sample city configurations
SAMPLE_CITIES_4 = [(0, 0), (1, 1), (2, 0), (1, -1)]
SAMPLE_CITIES_5 = [(0, 0), (1, 1), (2, 0), (1, -1), (0, 2)]
SAMPLE_CITIES_10 = [
    (0, 0),
    (1, 1),
    (2, 0),
    (1, -1),
    (0, 2),
    (3, 1),
    (2, 2),
    (3, 0),
    (4, 1),
    (3, -1),
]

# Sample diffs for testing evolution
SAMPLE_DIFF_SIMPLE = "return sorted(range(len(cities)), key=lambda x: x)"
SAMPLE_DIFF_COMPLEX = """# Nearest neighbor with improvements
n = len(cities)
if n <= 2:
    return list(range(n))

# Start from city 0
tour = [0]
unvisited = set(range(1, n))
current = 0

while unvisited:
    # Find nearest unvisited city
    distances = []
    for city in unvisited:
        dist = ((cities[current][0] - cities[city][0])**2 +
                (cities[current][1] - cities[city][1])**2)**0.5
        distances.append((dist, city))

    nearest_dist, nearest_city = min(distances)
    tour.append(nearest_city)
    unvisited.remove(nearest_city)
    current = nearest_city

return tour"""

# Mock LLM responses
MOCK_LLM_RESPONSES = {
    "simple_improvement": [SAMPLE_DIFF_SIMPLE],
    "complex_improvement": [SAMPLE_DIFF_COMPLEX],
    "invalid_response": ["This is not valid code"],
    "empty_response": [""],
    "syntax_error": ["return [i for i in range(len(cities)"],
}

# Sample prompts
SAMPLE_PROMPT_BASIC = """
Improve the following TSP solution:

### Current Code ###
def tsp(cities):
    return list(range(len(cities)))

### Instructions ###
Make the solution more efficient while keeping it valid.
"""

SAMPLE_PROMPT_COMPLEX = """
Improve the following TSP solution:

### Current Code ###
{current_code}

### Previous Children ###
{children}

### Instructions ###
{instructions}

Generate an improved version that reduces tour cost.
"""
