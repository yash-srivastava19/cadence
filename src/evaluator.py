import math
import random
from concurrent.futures import ThreadPoolExecutor


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

def execute_single_seed(seed, tsp_func):
    try:
        cities = generate_test_instance(seed=seed)
        tour = tsp_func(cities)

        if sorted(tour) != list(range(len(cities))):
            return float("inf")

        cost = compute_total_distance(tour, cities)
        return cost

    except Exception as e:
        return float("inf")

def execute(child_program_code: str, seeds: list[int] = [1, 2, 3, 4, 5]):
    try:
        # Load the tsp() function from the generated program
        local_env = {}
        exec(child_program_code, local_env)
        tsp_func = local_env.get("tsp")

        if tsp_func is None:
            return {"error": "No 'tsp' function found", "cost": float("inf")}

        with ThreadPoolExecutor(max_workers=len(seeds)) as executor:
            results = list(executor.map(lambda seed: execute_single_seed(seed, tsp_func), seeds))


        avg_cost = sum(results) / len(results)
        return {"cost": avg_cost}

    except Exception as e:
        return {"error": str(e), "cost": float("inf")}
