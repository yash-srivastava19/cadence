import json
import os
from hashlib import sha1
import numpy as np
import matplotlib.pyplot as plt
import hydra
import logging
from typing import List, Dict, Any
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
from src.meta_prompting import get_lesson_from_history
from concurrent.futures import ThreadPoolExecutor, TimeoutError

logger = logging.getLogger(__name__)


LESSON_HISTORY = []
LESSON_LOG_PATH = "lesson_history.json"


def save_lesson_history() -> None:
    """Save lesson history to disk."""
    try:
        with open(LESSON_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(LESSON_HISTORY, f, indent=2, ensure_ascii=False)
        logger.debug("Lesson history saved")
    except Exception as e:
        logger.error(f"Failed to save lesson history: {e}")


def run_size_experiment(
    size: int,
    generations: int,
    lesson_interval: int,
    API_MAX_RETRIES: int = 2,
    API_TIMEOUT: int = 60,
) -> List[Dict[str, Any]]:
    log = []

    # Load existing lesson history
    if os.path.exists(LESSON_LOG_PATH):
        try:
            with open(LESSON_LOG_PATH) as lf:
                LESSON_HISTORY.extend(json.load(lf))
        except Exception:
            LESSON_HISTORY.clear()
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

        # Determine lesson for this generation
        lesson = None
        if gen % lesson_interval == 0 and LESSON_HISTORY:
            lesson = LESSON_HISTORY[-1]
        # Build prompt including lesson
        prompt = build(parent, inspirations, lesson)
        # Generate diffs with timeout and retry
        diffs = None
        for attempt in range(API_MAX_RETRIES):
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(generate, prompt)
                    diffs = future.result(timeout=API_TIMEOUT)
                break
            except TimeoutError:
                logger.warning(
                    f"Size {size}, gen {gen}: LLM call timed out on attempt {attempt + 1}"
                )
            except Exception as e:
                logger.warning(
                    f"Size {size}, gen {gen}: LLM error on attempt {attempt + 1}: {e}"
                )
            if attempt == API_MAX_RETRIES - 1:
                logger.error(
                    f"Size {size}, gen {gen}: LLM failed after {API_MAX_RETRIES} attempts, aborting size experiment."
                )
                # Save partial log and lessons
                with open(f"h2_log_size_{size}.json", "w") as f:
                    json.dump(log, f, indent=2)
                with open(LESSON_LOG_PATH, "w") as lf:
                    json.dump(LESSON_HISTORY, lf, indent=2)
                return log
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
                "lesson": None,
            }
        )
        # Extract lessons periodically
        if gen % lesson_interval == 0:
            prev_lesson = LESSON_HISTORY[-1] if LESSON_HISTORY else None
            lesson = None
            for attempt in range(API_MAX_RETRIES):
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        # Pass N and previous_lesson to lesson extractor
                        future = executor.submit(
                            get_lesson_from_history,
                            log,
                            lesson_interval,
                            previous_lesson=prev_lesson,
                        )
                        lesson = future.result(timeout=API_TIMEOUT)
                    break
                except TimeoutError:
                    logger.warning(
                        f"Size {size}, gen {gen}: lesson extraction timed out on attempt {attempt + 1}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Size {size}, gen {gen}: lesson extraction error on attempt {attempt + 1}: {e}"
                    )
            if lesson:
                LESSON_HISTORY.append(lesson)
                save_lesson_history()
                log[-1]["lesson"] = lesson

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
    # Initialize collections for scaling analysis
    final_costs = {"llm": [], "nn": []}
    final_stds = []
    scaling_summary = []
    # Run experiments across sizes
    for size in cfg.SIZES:
        print(f"Running size={size}...")
        # Baseline heuristics
        base_mean, base_std = baseline_cost(size, seeds=cfg.SEEDS)
        final_costs["nn"].append(base_mean)
        final_stds.append(base_std)
        # LLM evolution
        LLOG = run_size_experiment(
            size,
            cfg.GENERATIONS,
            cfg.LESSON_INTERVAL,
            cfg.API_MAX_RETRIES,
            cfg.API_TIMEOUT,
        )
        final_cost = LLOG[-1]["cost"]
        final_costs["llm"].append(final_cost)
        # Save per-size logs
        with open(f"h2_log_size_{size}.json", "w") as f:
            json.dump(LLOG, f, indent=2)
        # Accumulate scaling metrics
        abs_imp = base_mean - final_cost
        rel_imp = abs_imp / base_mean if base_mean else 0.0
        scaling_summary.append(
            {
                "size": size,
                "baseline_mean": base_mean,
                "baseline_std": base_std,
                "llm_final": final_cost,
                "abs_improvement": abs_imp,
                "rel_improvement": rel_imp,
            }
        )
    # Persist scaling summary
    with open("h2_scaling_summary.json", "w") as sf:
        json.dump(scaling_summary, sf, indent=2)
    # Enhanced plots: cost curves with error bars and relative improvement
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(8, 10), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    # Top: tour cost curves
    ax1.errorbar(
        cfg.SIZES,
        final_costs["nn"],
        yerr=final_stds,
        marker="o",
        linestyle="-",
        label="Nearest Neighbor",
    )
    ax1.plot(
        cfg.SIZES, final_costs["llm"], marker="s", linestyle="--", label="LLM Evolution"
    )
    ax1.set_ylabel("Average Tour Cost")
    ax1.set_title("Hypothesis 2: Scaling Laws in LLM-based TSP")
    ax1.legend(loc="best")
    ax1.grid(True)
    # Bottom: relative improvement
    rels = [entry["rel_improvement"] for entry in scaling_summary]
    ax2.plot(cfg.SIZES, rels, marker="o", color="purple")
    ax2.set_xlabel("City Count")
    ax2.set_ylabel("Relative Improvement")
    ax2.set_title("LLM Relative Improvement vs Baseline")
    ax2.grid(True)
    plt.tight_layout()
    fig.savefig("h2_scaling_analysis.png")
    print("Saved h2_scaling_analysis.png and h2_scaling_summary.json")
    # Print summary table
    print("\nScaling Summary:")
    print("| City Count | NN Avg Cost | LLM Cost | Relative Improvement |")
    print("| ---------- | ----------- | -------- | -------------------- |")
    for entry in scaling_summary:
        size = entry["size"]
        base = entry["baseline_mean"]
        llm = entry["llm_final"]
        rel = entry["rel_improvement"] * 100
        print(f"| {size} | {base:.2f} | {llm:.2f} | {rel:.1f}% |")


if __name__ == "__main__":
    main()
