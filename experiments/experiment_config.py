# Experiment Configuration File
# This file defines the parameters for prompt strategy experiments

import json

# Experimental configurations
EXPERIMENT_CONFIG = {
    "experiment_name": "prompt_strategy_tsp_comparison",
    "description": "Comparing different prompt strategies across multiple TSP sizes",
    # Problem configurations
    "tsp_sizes": {"small": 8, "medium": 20, "large": 40},
    # Prompt strategies to test
    "prompt_strategies": {
        "greedy": {
            "instruction": "Focus on greedy heuristics and nearest neighbor approaches. Always make locally optimal choices by selecting the closest unvisited city. Prioritize simple construction methods that build tours step by step.",
            "keywords": [
                "nearest",
                "greedy",
                "closest",
                "minimum distance",
                "construction",
            ],
            "expected_patterns": [
                "nearest neighbor",
                "greedy selection",
                "distance minimization",
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
            "expected_patterns": [
                "2-opt",
                "local search",
                "iterative improvement",
                "swapping",
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
            "expected_patterns": [
                "graph theory",
                "optimization",
                "systematic approach",
                "mathematical formulation",
            ],
        },
    },
    # Experiment parameters
    "experiment_params": {
        "runs_per_config": 3,
        "generations_per_run": 10,
        "population_size": 1,
        "timeout_per_generation": 300,  # seconds
        "max_infeasible_cost": 1000,
    },
    # Analysis configuration
    "analysis_config": {
        "significance_level": 0.05,
        "convergence_threshold": 0.01,  # 1% improvement threshold
        "plot_confidence_intervals": True,
        "save_individual_runs": True,
    },
    # Expected hypotheses to test
    "hypotheses": [
        {
            "name": "H1_strategy_effectiveness",
            "description": "Different prompt strategies will show significantly different performance",
            "prediction": "Search-based prompts will outperform greedy-based prompts on larger problems",
        },
        {
            "name": "H2_size_scaling",
            "description": "Strategy effectiveness will vary with problem size",
            "prediction": "Mathematical prompts will scale better to larger problems",
        },
        {
            "name": "H3_convergence_speed",
            "description": "Different strategies will converge at different rates",
            "prediction": "Greedy strategies will converge faster but to worse solutions",
        },
    ],
    # Baseline comparisons
    "baselines": {
        "random_tour": "Random permutation of cities",
        "nearest_neighbor": "Classic nearest neighbor heuristic",
        "naive_greedy": "Simple greedy construction",
    },
}


# Validation functions
def validate_config(config):
    """Validate experiment configuration"""
    required_keys = ["tsp_sizes", "prompt_strategies", "experiment_params"]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: {key}")

    # Validate TSP sizes
    for size_name, size_value in config["tsp_sizes"].items():
        if not isinstance(size_value, int) or size_value < 3:
            raise ValueError(f"Invalid TSP size for {size_name}: {size_value}")

    # Validate strategies
    for strategy_name, strategy_config in config["prompt_strategies"].items():
        required_strategy_keys = ["instruction", "keywords"]
        for key in required_strategy_keys:
            if key not in strategy_config:
                raise ValueError(f"Missing key '{key}' in strategy '{strategy_name}'")

    print("Configuration validation passed!")
    return True


def save_config(config, filename="experiment_config.json"):
    """Save configuration to JSON file"""
    with open(filename, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved to {filename}")


def load_config(filename="experiment_config.json"):
    """Load configuration from JSON file"""
    with open(filename, "r") as f:
        config = json.load(f)
    validate_config(config)
    return config


if __name__ == "__main__":
    # Validate and save the default configuration
    validate_config(EXPERIMENT_CONFIG)
    save_config(EXPERIMENT_CONFIG)

    print("\nExperiment Configuration Summary:")
    print(f"- TSP sizes: {list(EXPERIMENT_CONFIG['tsp_sizes'].keys())}")
    print(f"- Strategies: {list(EXPERIMENT_CONFIG['prompt_strategies'].keys())}")
    print(
        f"- Runs per config: {EXPERIMENT_CONFIG['experiment_params']['runs_per_config']}"
    )
    print(
        f"- Total experiments: {len(EXPERIMENT_CONFIG['tsp_sizes']) * len(EXPERIMENT_CONFIG['prompt_strategies']) * EXPERIMENT_CONFIG['experiment_params']['runs_per_config']}"
    )
