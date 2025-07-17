"""
Hypothesis 1: How good are LLMs at designing heuristics for the TSP?

This script:
1. Runs baseline heuristics (e.g., Nearest Neighbor).
2. Evolves programs using your LLM system.
3. Logs and compares costs over generations.
4. Based on the heuristic feedback, guides the LLMs to improve.
4. Visualizes results and see the improvement.

Usage:
"""

import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import matplotlib.pyplot as plt
from hashlib import sha1
from tqdm.rich import trange
import hydra
from omegaconf import DictConfig
from src.tasks.tsp_task import TSPTask
from src.tasks.tsp_reference import nearest_neighbor, reversed_tour
from src.evaluator import generate_test_instance, compute_total_distance
from src.database import add, sample
from src.evolve import apply_diff
from src.evaluator import execute
from src.prompt_sampler import build
from src.llm import generate
from src.evaluator import INFEASIBLE_COST
from src.meta_prompting import get_lesson_from_history

LESSON_HISTORY = []
LESSON_LOG_PATH = "lesson_history.json"

EXPERIMENT_LOG = []
HASHES = set()

logger = logging.getLogger(__name__)


def save_lesson_history() -> None:
    """Save lesson history to disk."""
    try:
        with open(LESSON_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(LESSON_HISTORY, f, indent=2, ensure_ascii=False)
        logger.debug("Lesson history saved")
    except Exception as e:
        logger.error(f"Failed to save lesson history: {e}")


def run_baselines(n_seeds: int):
    nn_scores, rev_scores = [], []
    for seed in range(n_seeds):
        cities = generate_test_instance(seed=seed)
        nn = nearest_neighbor(cities)
        rev = reversed_tour(cities)
        nn_scores.append(compute_total_distance(nn, cities))
        rev_scores.append(compute_total_distance(rev, cities))
    return nn_scores, rev_scores


def run_llm_evolution(
    n_generations, lesson_interval, API_MAX_RETRIES=2, API_TIMEOUT=60
):
    global EXPERIMENT_LOG, HASHES, LESSON_HISTORY
    task = TSPTask()
    # Load existing lesson history
    if os.path.exists(LESSON_LOG_PATH):
        try:
            with open(LESSON_LOG_PATH) as f:
                LESSON_HISTORY = json.load(f)
        except Exception:
            LESSON_HISTORY = []
    if not os.path.exists("experiment_log.json"):
        baseline_metric = execute(task.baseline_program, task)["cost"]
        add(program_code=task.baseline_program, metric=baseline_metric)
        print(f"Baseline added with cost: {baseline_metric:.2f}")

    for generation in trange(1, n_generations + 1):
        parent, inspirations = sample(generation_number=generation)
        if not parent:
            print(f"[!] No parent for generation {generation}")
            continue

        # Determine lesson for this generation, if any
        # Determine and pass the latest lesson into the prompt (modeling main.py behavior)
        lesson = None
        if generation % lesson_interval == 0:
            # Use most recent lesson or None
            previous_lesson = LESSON_HISTORY[-1] if LESSON_HISTORY else None
            lesson = previous_lesson
        if generation % lesson_interval == 0 and LESSON_HISTORY:
            lesson = LESSON_HISTORY[-1]
            logger.info(f"Extracting lesson for generation {generation}: {lesson}")
        # Build prompt including lesson when available
        prompt = build(parent, inspirations, lesson)
        diffs = None
        for attempt in range(API_MAX_RETRIES):
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(generate, prompt)
                    diffs = future.result(timeout=API_TIMEOUT)
                break
            except TimeoutError:
                logger.warning(
                    f"Generation {generation}: LLM call timed out on attempt {attempt + 1}"
                )
            except Exception as e:
                logger.warning(
                    f"Generation {generation}: LLM error on attempt {attempt + 1}: {e}"
                )
            if attempt == API_MAX_RETRIES - 1:
                logger.error(
                    f"Generation {generation}: LLM failed after {API_MAX_RETRIES} attempts, saving progress and aborting."
                )
                # Save logs up to this point
                with open("experiment_log.json", "w") as f:
                    json.dump(EXPERIMENT_LOG, f, indent=2)
                with open(LESSON_LOG_PATH, "w") as lf:
                    json.dump(LESSON_HISTORY, lf, indent=2)
                return
        if diffs is None:
            continue

        # Apply diff and evaluate
        child_code = apply_diff(parent[3], diffs)
        code_hash = sha1(child_code.encode()).hexdigest()
        HASHES.add(code_hash)
        parent_cost = parent[4] if len(parent) > 4 else None
        metric = execute(child_code, task)
        add(parent_id=parent[0], program_code=child_code, metric=metric["cost"])
        # Log generation details including parent vs child
        entry = {
            "generation": generation,
            "parent_cost": parent_cost,
            "child_cost": metric["cost"],
            "feasibility": metric.get("feasibility_ratio", 0.0),
            "hash": code_hash,
            "parent_code": parent[3],
            "child_code": child_code,
            "lesson": None,
        }
        EXPERIMENT_LOG.append(entry)

        # Extract lessons periodically with timeout and retries
        if generation % lesson_interval == 0:
            logger.info(f"Extracting lesson for generation {generation}...")
            previous_lesson = LESSON_HISTORY[-1] if LESSON_HISTORY else None
            lesson = None
            for attempt in range(API_MAX_RETRIES):
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            get_lesson_from_history,
                            EXPERIMENT_LOG,
                            previous_lesson=previous_lesson,
                        )
                        lesson = future.result(timeout=API_TIMEOUT)
                    break
                except TimeoutError:
                    logger.warning(
                        f"Generation {generation}: lesson extraction timed out on attempt {attempt + 1}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Generation {generation}: lesson extraction error on attempt {attempt + 1}: {e}"
                    )
                if attempt == API_MAX_RETRIES - 1:
                    logger.error(
                        f"Generation {generation}: lesson extraction failed after {API_MAX_RETRIES} attempts"
                    )
            if lesson:
                LESSON_HISTORY.append(lesson)
                logger.info(f"New lesson extracted: {lesson}")
                save_lesson_history()
                entry["lesson"] = lesson

    with open("experiment_log.json", "w") as f:
        json.dump(EXPERIMENT_LOG, f, indent=2)


def plot_results(nn_scores, rev_scores, log_path="experiment_log.json"):
    with open(log_path) as f:
        logs = json.load(f)

    gens = [e["generation"] for e in logs]
    costs = [e["child_cost"] if "child_cost" in e else e.get("cost") for e in logs]
    # Separate feasible and infeasible
    feasible = [(g, c) for g, c in zip(gens, costs) if c < INFEASIBLE_COST]
    infeasible = [(g, c) for g, c in zip(gens, costs) if c >= INFEASIBLE_COST]
    feas_g, feas_c = zip(*feasible) if feasible else ([], [])
    infeas_g, _ = zip(*infeasible) if infeasible else ([], [])

    # Create subplots: cost evolution and delta improvements
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 10), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    # Top: cost evolution
    ax1.plot(feas_g, feas_c, marker="o", label="LLM Evolved (feasible)")
    if infeasible:
        ax1.scatter(
            infeas_g,
            [min(feas_c) * 0.9] * len(infeas_g),
            marker="x",
            color="red",
            label="Infeasible",
        )
    ax1.axhline(
        y=sum(nn_scores) / len(nn_scores),
        color="g",
        linestyle="--",
        label="Nearest Neighbor",
    )
    # (Optional) Remove reversed baseline to focus on nearest neighbor and evolved
    ax1.set_ylabel("Tour Cost")
    ax1.set_title("Hypothesis 1: LLM Evolution vs Baselines")
    ax1.legend(loc="upper right")
    ax1.grid(True)
    # Bottom: delta cost (parent_cost - child_cost)
    # Bottom: lesson-driven cost deltas only (feasible)
    delta_gens, deltas = [], []
    for entry in logs:
        lesson = entry.get("lesson")
        p = entry.get("parent_cost")
        c = entry.get("child_cost")
        # Only plot when a lesson was applied and cost is feasible
        if not lesson or p is None or c is None or c >= INFEASIBLE_COST:
            continue
        delta_gens.append(entry["generation"])
        deltas.append(p - c)
    if delta_gens:
        bars = ax2.bar(
            delta_gens, deltas, color=["green" if d > 0 else "red" for d in deltas]
        )
        # Annotate each bar with the lesson text
        for bar, gen in zip(bars, delta_gens):
            lesson = next(e["lesson"] for e in logs if e["generation"] == gen)
            ax2.annotate(
                lesson,
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax2.set_xlabel("Generation")
    ax2.set_ylabel("Δ Cost")
    ax2.set_title("Lesson-driven Cost Improvements")
    ax2.grid(True)
    plt.tight_layout()
    fig.savefig("h1_results.png")
    print("Saved combined plot to h1_results.png")


@hydra.main(version_base=None, config_path="conf", config_name="h1_config")
def main(cfg: DictConfig) -> None:
    print("[1] Running baseline heuristics...")
    nn_scores, rev_scores = run_baselines(cfg.SEEDS)

    print("[2] Running LLM evolution...")
    run_llm_evolution(
        cfg.GENERATIONS, cfg.LESSON_INTERVAL, cfg.API_MAX_RETRIES, cfg.API_TIMEOUT
    )

    print("[3] Plotting results...")
    plot_results(nn_scores, rev_scores)


if __name__ == "__main__":
    main()
