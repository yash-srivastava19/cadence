import json
from hashlib import sha1
import numpy as np
import matplotlib.pyplot as plt
import hydra
import logging
from omegaconf import DictConfig
from tqdm.rich import trange
from src.tasks.tsp_task import TSPTask
from src.tasks.tsp_reference import nearest_neighbor
from src.evaluator import generate_test_instance, compute_total_distance
from src.database import add, sample
from src.evolve import apply_diff
from src.evaluator import execute
from src.prompt_sampler import build
from src.llm import generate

logger = logging.getLogger(__name__)


def run_size_experiment(size: int, generations: int):
    log = []

    # 1) Create task and evaluator, then seed baseline entry
    task = TSPTask(n_cities=size)
    baseline_code = task.baseline_program
    baseline_res = execute(baseline_code, task)
    add(parent_id=None, program_code=baseline_code, metric=baseline_res["cost"])
    baseline_hash = sha1(baseline_code.encode()).hexdigest()
    log.append(
        {
            "gen": 0,
            "cost": baseline_res["cost"],
            "feas": baseline_res["feasibility"],
            "hash": baseline_hash,
        }
    )

    # 2) Now run LLM evolution starting from gen=1
    for gen in trange(1, generations):
        # sample parent from previous generation
        parent, inspirations = sample(generation_number=gen - 1)
        if parent is None:
            # fall back to baseline if something went wrong
            parent = (None, None, None, baseline_code, baseline_res["cost"])

        prompt = build(parent, inspirations)
        diffs = generate(prompt)
        if not diffs:
            continue

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
        cities = generate_test_instance(n=size, seed=seed)
        tour = nearest_neighbor(cities)
        scores.append(compute_total_distance(tour, cities))
    return np.mean(scores), np.std(scores)


@hydra.main(config_path="conf", config_name="h2_config")
def main(cfg: DictConfig):
    final_costs = {"llm": [], "nn": []}
    for size in cfg.SIZES:
        print(f"Running size={size}...")
        base_mean, base_std = baseline_cost(size, seeds=cfg.SEEDS)
        final_costs["nn"].append(base_mean)

        LLOG = run_size_experiment(size, cfg.GENERATIONS)
        final_cost = LLOG[-1]["cost"]
        final_costs["llm"].append(final_cost)

        with open(f"h2_log_size_{size}.json", "w") as f:
            json.dump(LLOG, f, indent=2)

    # Plot scaling curves
    plt.figure(figsize=(8, 5))
    plt.plot(cfg.SIZES, final_costs["nn"], label="Nearest‑Neighbor")
    plt.plot(cfg.SIZES, final_costs["llm"], label="LLM Evolution")
    plt.xlabel("City Count")
    plt.ylabel("Average Tour Cost")
    plt.title("Hypothesis 2: Scaling Laws in LLM‑based TSP")
    plt.legend()
    plt.grid(True)
    plt.savefig("h2_scaling_curve.png")
    print("Saved h2_scaling_curve.png")


if __name__ == "__main__":
    main()
