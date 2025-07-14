"""
Hypothesis 1: How good are LLMs at designing heuristics for the TSP?

This script:
1. Runs baseline heuristics (e.g., Nearest Neighbor)
2. Evolves programs using your LLM system
3. Logs and compares costs over generations
4. Visualizes results

Usage:
    python run_h1_experiment.py --generations 20 --seeds 10
"""

import os
import json
import argparse
import matplotlib.pyplot as plt
from hashlib import sha1
from tqdm import tqdm

from src.tasks.tsp_task import TSPTask
from src.tasks.tsp_reference import nearest_neighbor, reversed_tour
from src.evaluator import generate_test_instance, compute_total_distance
from src.database import add, sample
from src.evolve import apply_diff
from src.evaluator import execute
from src.prompt_sampler import build
from src.llm import generate

EXPERIMENT_LOG = []
HASHES = set()


def run_baselines(n_seeds):
    nn_scores, rev_scores = [], []
    for seed in range(n_seeds):
        cities = generate_test_instance(seed=seed)
        nn = nearest_neighbor(cities)
        rev = reversed_tour(cities)
        nn_scores.append(compute_total_distance(nn, cities))
        rev_scores.append(compute_total_distance(rev, cities))
    return nn_scores, rev_scores


def run_llm_evolution(n_generations, seeds_per_eval=5):
    global EXPERIMENT_LOG, HASHES
    task = TSPTask()
    if not os.path.exists("experiment_log.json"):
        baseline_metric = execute(task.baseline_program)["cost"]
        add(program_code=task.baseline_program, metric=baseline_metric)
        print(f"Baseline added with cost: {baseline_metric:.2f}")

    for generation in tqdm(range(n_generations)):
        parent, inspirations = sample(generation_number=generation)
        if not parent:
            print(f"[!] No parent for generation {generation}")
            continue

        prompt = build(parent, inspirations)
        try:
            diffs = generate(prompt)
        except Exception as e:
            print(f"LLM failed: {e}")
            continue

        child_code = apply_diff(parent[3], diffs)
        code_hash = sha1(child_code.encode()).hexdigest()
        HASHES.add(code_hash)

        metric = execute(child_code, task)
        add(parent_id=parent[0], program_code=child_code, metric=metric["cost"])

        EXPERIMENT_LOG.append(
            {
                "generation": generation,
                "cost": metric["cost"],
                "feasibility": metric.get("feasibility_ratio", 0.0),
                "hash": code_hash,
                "program_code": child_code,
            }
        )

    with open("experiment_log.json", "w") as f:
        json.dump(EXPERIMENT_LOG, f, indent=2)


def plot_results(nn_scores, rev_scores, log_path="experiment_log.json"):
    with open(log_path) as f:
        logs = json.load(f)

    gens = [e["generation"] for e in logs]
    costs = [e["cost"] for e in logs]

    plt.figure(figsize=(10, 6))
    plt.plot(gens, costs, label="LLM Evolved")
    plt.axhline(
        y=sum(nn_scores) / len(nn_scores),
        color="g",
        linestyle="--",
        label="Nearest Neighbor",
    )
    plt.axhline(
        y=sum(rev_scores) / len(rev_scores), color="r", linestyle="--", label="Reversed"
    )

    plt.xlabel("Generation")
    plt.ylabel("Tour Cost")
    plt.title("Hypothesis 1: LLM-Generated TSP Heuristics vs Baselines")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("h1_results.png")
    print("Saved plot to h1_results.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--generations", type=int, default=20, help="Number of generations to evolve"
    )
    parser.add_argument(
        "--seeds", type=int, default=10, help="Number of test seeds for baselines"
    )
    args = parser.parse_args()

    print("[1] Running baseline heuristics...")
    nn, rev = run_baselines(args.seeds)

    print("[2] Running LLM evolution...")
    run_llm_evolution(args.generations)

    print("[3] Plotting results...")
    plot_results(nn, rev)
