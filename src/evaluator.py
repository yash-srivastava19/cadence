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

def execute(child_program_code: str, seeds: list[int] = [1, 2, 3, 4, 5]):
    total_cost = 0
    errors = []

    try:
        # Load the tsp() function from the generated program
        local_env = {}
        exec(child_program_code, local_env)
        tsp_func = local_env.get("tsp")

        if tsp_func is None:
            return {"error": "No 'tsp' function found", "cost": float("inf")}

        for seed in seeds:
            try:
                cities = generate_test_instance(seed = seed)
                tour = tsp_func(cities)

                # Validate tour
                if sorted(tour) != list(range(len(cities))):
                    errors.append(f"Invalid tour at seed {seed}")
                    total_cost += float("inf")
                    continue

                cost = compute_total_distance(tour, cities)
                total_cost += cost

            except Exception as inner_e:
                errors.append(f"Seed {seed} error: {inner_e}")
                total_cost += float("inf")

        avg_cost = total_cost / len(seeds)
        return {"cost": avg_cost, "errors": errors if errors else None}

    except Exception as e:
        return {"error": str(e), "cost": float("inf")}
