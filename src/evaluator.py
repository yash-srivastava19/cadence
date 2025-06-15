import math
import random

def euclidean(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def compute_total_distance(tour, cities):
    distance = 0
    for i in range(len(tour)):
        a = cities[tour[i]]
        b = cities[tour[(i + 1) % len(tour)]]  # wrap around
        distance += euclidean(a, b)
    return distance

def generate_test_instance(n=10, seed=42):
    random.seed(seed)
    return [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n)]

def execute(child_program_code: str):
    try:
        # Step 1: Create input instance
        cities = generate_test_instance()

        # Step 2: Define environment and run child program
        local_env = {}
        exec(child_program_code,local_env)
        tsp_func = local_env.get("tsp")
        if tsp_func is None:
            return {"error": "No 'tsp' function found", "cost": float("inf")}

        tour = tsp_func(cities)

        # Step 3: Validate and evaluate tour
        if sorted(tour) != list(range(len(cities))):
            return {"error": "Invalid tour", "cost": float("inf")}

        cost = compute_total_distance(tour, cities)
        return {"cost": cost}

    except Exception as e:
        return {"error": str(e), "cost": float("inf")}


## Assumptions:
# We’ll assume the child_program is a Python string containing a function def tsp(cities): ... and that: cities is a list of (x, y) tuples.

# The returned tour is a list of indices (a permutation of [0, ..., n-1]).
