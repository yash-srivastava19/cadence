#!/usr/bin/env python3
"""
Prompt Strategy Experiment Runner

This script runs the complete prompt strategy experiment, including:
1. Running all experiment configurations
2. Analyzing results
3. Generating reports and visualizations

Usage:
    python run_experiment.py [--config config_file] [--analysis-only results_file]
"""

import argparse
import os
import sys
import json
from datetime import datetime
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment_config import EXPERIMENT_CONFIG, validate_config, load_config
from prompt_strategy_experiment import PromptStrategyExperiment
from experiment_analysis import create_comprehensive_analysis


def setup_logging(log_dir):
    """Setup logging configuration"""
    log_file = os.path.join(log_dir, "experiment_runner.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )

    return logging.getLogger(__name__)


def create_experiment_summary(config, results_dir):
    """Create experiment summary document"""
    summary = f"""
# Prompt Strategy Experiment Summary

**Experiment ID:** {os.path.basename(results_dir)}
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Experiment Configuration

### Problem Sizes Tested:
{chr(10).join(f"- {name}: {size} cities" for name, size in config["tsp_sizes"].items())}

### Prompt Strategies:
{chr(10).join(f"- **{name}**: {strategy['instruction'][:100]}..." for name, strategy in config["prompt_strategies"].items())}

### Parameters:
- Runs per configuration: {config["experiment_params"]["runs_per_config"]}
- Generations per run: {config["experiment_params"]["generations_per_run"]}
- Total experiments: {len(config["tsp_sizes"]) * len(config["prompt_strategies"]) * config["experiment_params"]["runs_per_config"]}

## Hypotheses Tested:
{chr(10).join(f"- **{h['name']}**: {h['description']}" for h in config.get("hypotheses", []))}

## Expected Outcomes:
The experiment aims to determine which prompt engineering strategies are most effective for evolving TSP solutions across different problem sizes.

## Files Generated:
- `final_results.json`: Complete experimental results
- `statistical_report.txt`: Statistical analysis
- `summary_table.csv`: Tabular summary of all runs
- `strategy_comparison.png`: Performance comparison visualization
- `convergence_curves.png`: Convergence analysis
"""

    with open(os.path.join(results_dir, "experiment_summary.md"), "w") as f:
        f.write(summary)


def run_full_experiment(config_file=None):
    """Run the complete experiment pipeline"""
    # Load configuration
    if config_file:
        config = load_config(config_file)
    else:
        config = EXPERIMENT_CONFIG
        validate_config(config)

    # Create experiment instance
    experiment = PromptStrategyExperiment()
    logger = setup_logging(experiment.results_dir)

    logger.info("Starting prompt strategy experiment")
    logger.info(f"Results directory: {experiment.results_dir}")

    # Save configuration used
    config_path = os.path.join(experiment.results_dir, "experiment_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Create experiment summary
    create_experiment_summary(config, experiment.results_dir)

    try:
        # Run experiments
        logger.info("Running experiments...")
        results = experiment.run_all_experiments()

        if not results:
            logger.error("No experimental results generated!")
            return None

        logger.info(f"Experiments completed. {len(results)} results generated.")

        # Run analysis
        logger.info("Analyzing results...")
        results_file = os.path.join(experiment.results_dir, "final_results.json")
        analysis_dir = os.path.join(experiment.results_dir, "analysis")

        create_comprehensive_analysis(results_file, analysis_dir)

        logger.info("Experiment and analysis completed successfully!")
        return experiment.results_dir

    except Exception as e:
        logger.error(f"Experiment failed: {e}")
        raise


def analyze_existing_results(results_file):
    """Analyze existing experiment results"""
    if not os.path.exists(results_file):
        print(f"Error: Results file not found: {results_file}")
        return

    # Create analysis directory
    results_dir = os.path.dirname(results_file)
    analysis_dir = os.path.join(results_dir, "analysis")

    print(f"Analyzing results from: {results_file}")
    create_comprehensive_analysis(results_file, analysis_dir)
    print(f"Analysis completed. Results saved to: {analysis_dir}")


def main():
    parser = argparse.ArgumentParser(description="Run prompt strategy experiments")
    parser.add_argument("--config", help="Path to experiment configuration file")
    parser.add_argument(
        "--analysis-only", help="Only run analysis on existing results file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without running experiments",
    )

    args = parser.parse_args()

    if args.analysis_only:
        analyze_existing_results(args.analysis_only)
    elif args.dry_run:
        config = load_config(args.config) if args.config else EXPERIMENT_CONFIG
        print("Configuration validation passed!")
        print(
            f"Total experiments that would be run: {len(config['tsp_sizes']) * len(config['prompt_strategies']) * config['experiment_params']['runs_per_config']}"
        )
    else:
        results_dir = run_full_experiment(args.config)
        if results_dir:
            print(f"\n{'=' * 60}")
            print("EXPERIMENT COMPLETED SUCCESSFULLY!")
            print(f"{'=' * 60}")
            print(f"Results directory: {results_dir}")
            print(f"View analysis: {os.path.join(results_dir, 'analysis')}")
            print(
                f"Statistical report: {os.path.join(results_dir, 'analysis', 'statistical_report.txt')}"
            )


if __name__ == "__main__":
    main()
