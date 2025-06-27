import math
import random
from concurrent.futures import ThreadPoolExecutor

INFEASIBLE_COST = 1e8


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

        is_feasible = isinstance(tour, list) and sorted(tour) == list(
            range(len(cities))
        )
        if not is_feasible:
            return {"cost": INFEASIBLE_COST, "feasible": False}

        cost = compute_total_distance(tour, cities)
        return {"cost": cost, "feasible": True}

    except Exception:
        return {
            "cost": INFEASIBLE_COST,
            "feasible": False,
        }


def execute(child_program_code: str, task, seeds: list[int] = [1, 2, 3, 4, 5]):
    try:
        from statistics import mean

        local_env = {}
        results = []
        exec(child_program_code, local_env)
        func = local_env.get(task.function_name)

        if not callable(func):
            return {"cost": INFEASIBLE_COST, "feasibility": 0.0}

        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(execute_single_seed, seed, func) for seed in seeds
            ]
            results = [future.result() for future in futures]

        avg_cost = mean(r["cost"] for r in results)
        feasibility_ratio = sum(1 for r in results if r["feasible"]) / len(results)

        return {
            "cost": avg_cost,
            "feasibility": feasibility_ratio,
        }

    except Exception:
        return {"cost": INFEASIBLE_COST, "feasibility": False}
