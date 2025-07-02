import json
import os
from datetime import datetime
import logging

from src.database import sample, add
from src.tasks.tsp_task import TSPTask
from src.evaluator import execute
from src.llm import generate
from src.prompt_sampler import build
from src.evolve import apply_diff

# Experiment configuration
PROMPT_STRATEGIES = {
    "greedy": {
        "instruction": "Focus on greedy heuristics and nearest neighbor approaches. Always make locally optimal choices by selecting the closest unvisited city. Prioritize simple construction methods that build tours step by step.",
        "keywords": [
            "nearest",
            "greedy",
            "closest",
            "minimum distance",
            "construction",
        ],
    },
    "search": {
        "instruction": "Emphasize local search and iterative improvement. Start with any solution, then systematically improve using swaps, insertions, and local optimization techniques like 2-opt.",
        "keywords": [
            "improve",
            "optimize",
            "swap",
            "local search",
            "2-opt",
            "iterative",
        ],
    },
    "mathematical": {
        "instruction": "Apply rigorous mathematical and graph theory concepts. Consider the TSP as a graph optimization problem requiring systematic algorithmic approaches and formal optimization methods.",
        "keywords": [
            "graph",
            "optimization",
            "algorithm",
            "mathematical",
            "systematic",
            "theory",
        ],
    },
}

TSP_SIZES = {"small": 8, "medium": 20, "large": 40}

RUNS_PER_CONFIG = 3  # Number of runs for each (strategy, size) combination
GENERATIONS_PER_RUN = 5  # Generations to run for each experiment


class PromptStrategyExperiment:
    def __init__(self):
        self.results = {}
        self.experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create results directory
        self.results_dir = f"experiments/results_{self.experiment_id}"
        os.makedirs(self.results_dir, exist_ok=True)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(f"{self.results_dir}/experiment.log"),
                logging.StreamHandler(),
            ],
        )

    def run_single_experiment(
        self, strategy_name, strategy_config, tsp_size, run_number
    ):
        """Run a single experiment configuration"""
        logging.info(
            f"Starting {strategy_name} strategy on {tsp_size}-city TSP (Run {run_number})"
        )

        # Create TSP task with specified size
        task = TSPTask(n_cities=TSP_SIZES[tsp_size])

        # Initialize database with baseline
        baseline_metric = execute(task.baseline_program, task)["cost"]
        add(program_code=task.baseline_program, metric=baseline_metric, parent_id=None)

        experiment_log = []
        best_cost = baseline_metric

        for generation in range(1, GENERATIONS_PER_RUN + 1):
            # Sample parent from previous generation
            parent_program, inspirations = sample(generation_number=generation - 1)

            if not parent_program:
                logging.warning(f"No parent found for generation {generation}")
                continue

            # Build prompt with strategy-specific instruction
            prompt = self.build_strategy_prompt(
                parent_program, inspirations, strategy_config
            )

            # Generate new program
            import time

            logging.info("Delaying generation to avoid rate limits...")
            time.sleep(2)
            response = generate(prompt)
            diffs = self.extract_diffs(response)

            if not diffs:
                logging.warning(f"No diffs extracted for generation {generation}")
                continue

            # Apply diffs to create child program
            child_program = apply_diff(
                parent_program[3], diffs
            )  # program_code at index 3

            # Evaluate child program
            metric = execute(child_program, task)
            cost = metric["cost"]

            # Store in database
            add(parent_id=parent_program[0], program_code=child_program, metric=cost)

            # Track best cost
            if cost < best_cost:
                best_cost = cost

            # Log results
            experiment_log.append(
                {
                    "generation": generation,
                    "cost": cost,
                    "best_so_far": best_cost,
                    "feasible": metric.get("feasibility", True),
                }
            )

            logging.info(f"Gen {generation}: Cost={cost:.2f}, Best={best_cost:.2f}")

        return {
            "strategy": strategy_name,
            "tsp_size": tsp_size,
            "run_number": run_number,
            "baseline_cost": baseline_metric,
            "final_best_cost": best_cost,
            "improvement": (baseline_metric - best_cost) / baseline_metric * 100,
            "log": experiment_log,
        }

    def build_strategy_prompt(self, parent_program, inspirations, strategy_config):
        """Build a prompt with strategy-specific instructions"""
        base_prompt = build(parent_program, inspirations)

        strategy_prompt = f"""
{strategy_config["instruction"]}

Focus on these concepts: {", ".join(strategy_config["keywords"])}

{base_prompt}

Generate improved code following the strategy above.
"""
        return strategy_prompt

    def extract_diffs(self, response):
        """Extract code diffs from LLM response - simplified for now"""
        import re

        if isinstance(response, list):
            response = "\n".join(response)

        response = str(response)
        # Extract code blocks wrapped in triple backticks
        code_blocks = re.findall(r"```(?:python)?\s*(.*?)```", response, re.DOTALL)

        if code_blocks:
            return [block.strip() for block in code_blocks if block.strip()]

        # Fallback: treat entire response as single diff
        return [response.strip()] if response.strip() else []

    def run_all_experiments(self):
        """Run all experiment combinations"""
        all_results = []

        for strategy_name, strategy_config in PROMPT_STRATEGIES.items():
            for tsp_size in TSP_SIZES.keys():
                for run_num in range(1, RUNS_PER_CONFIG + 1):
                    try:
                        result = self.run_single_experiment(
                            strategy_name, strategy_config, tsp_size, run_num
                        )
                        all_results.append(result)

                        # Save intermediate results
                        with open(
                            f"{self.results_dir}/intermediate_results.json", "w"
                        ) as f:
                            json.dump(all_results, f, indent=2, default=str)

                    except Exception as e:
                        logging.error(
                            f"Failed experiment {strategy_name}-{tsp_size}-{run_num}: {e}"
                        )
                        continue

        # Save final results
        with open(f"{self.results_dir}/final_results.json", "w") as f:
            json.dump(all_results, f, indent=2)

        self.results = all_results
        return all_results


if __name__ == "__main__":
    experiment = PromptStrategyExperiment()
    results = experiment.run_all_experiments()
    print(f"Experiment completed. Results saved to: {experiment.results_dir}")
