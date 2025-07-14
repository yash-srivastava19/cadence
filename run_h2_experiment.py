import argparse
import json
from hashlib import sha1
import numpy as np
import matplotlib.pyplot as plt

from src.tasks.tsp_task import TSPTask
from src.tasks.tsp_reference import nearest_neighbor
from src.evaluator import generate_test_instance, compute_total_distance
from src.database import add, sample
from src.evolve import apply_diff
from src.evaluator import execute
from src.prompt_sampler import build
from src.llm import generate


def run_size_experiment(size, generations, seeds_per_eval):
    # Override global task problem size here (depends on your task implementation)
    # e.g., tasks.tsp.CITY_COUNT = size

    log = []
    task = TSPTask(n_cities=size)
    for gen in range(generations):
        parent, inspirations = sample(generation_number=gen)
        prompt = build(parent, inspirations)
        diffs = generate(prompt)
        child_code = apply_diff(parent[3], diffs)
        code_hash = sha1(child_code.encode()).hexdigest()
        metric = execute(child_code, task)
        add(parent_id=parent[0], program_code=child_code, metric=metric["cost"])
        log.append(
            {
                "gen": gen,
                "cost": metric["cost"],
                "feas": metric["feasibility"],
                "hash": code_hash,
            }
        )
    return log


def baseline_cost(size, seeds=3):
    scores = []
    for seed in range(seeds):
        cities = generate_test_instance(seed=seed)
        tour = nearest_neighbor(cities)
        scores.append(compute_total_distance(tour, cities))
    return np.mean(scores), np.std(scores)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[10, 15, 20, 25])
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--seeds", type=int, default=10)
    args = parser.parse_args()

    final_costs = {"llm": [], "nn": []}
    for size in args.sizes:
        print(f"Running size={size}...")
        # Set task size
        # tasks.tsp.CITY_COUNT = size

        base_mean, base_std = baseline_cost(size, seeds=args.seeds)
        final_costs["nn"].append(base_mean)

        LLOG = run_size_experiment(size, args.generations, args.seeds)
        final_cost = LLOG[-1]["cost"]
        final_costs["llm"].append(final_cost)

        with open(f"h2_log_size_{size}.json", "w") as f:
            json.dump(LLOG, f, indent=2)

    # Plot scaling curves
    plt.figure(figsize=(8, 5))
    plt.plot(args.sizes, final_costs["nn"], label="Nearest‑Neighbor")
    plt.plot(args.sizes, final_costs["llm"], label="LLM Evolution")
    plt.xlabel("City Count")
    plt.ylabel("Average Tour Cost")
    plt.title("Hypothesis 2: Scaling Laws in LLM‑based TSP")
    plt.legend()
    plt.grid(True)
    plt.savefig("h2_scaling_curve.png")
    print("Saved h2_scaling_curve.png")
