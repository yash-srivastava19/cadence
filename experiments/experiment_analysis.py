import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Any


def load_experiment_results(results_file: str) -> List[Dict[str, Any]]:
    """Load experiment results from JSON file"""
    with open(results_file, "r") as f:
        return json.load(f)


def create_summary_table(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """Create summary table of all experiments"""
    summary = []

    for result in results:
        summary.append(
            {
                "Strategy": result["strategy"],
                "TSP_Size": result["tsp_size"],
                "Run": result["run_number"],
                "Baseline_Cost": result["baseline_cost"],
                "Final_Best_Cost": result["final_best_cost"],
                "Improvement_%": result["improvement"],
                "Generations": len(result["log"]),
            }
        )

    df = pd.DataFrame(summary)
    return df


def analyze_convergence(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze convergence patterns for each strategy"""
    convergence_analysis = {}

    for result in results:
        strategy = result["strategy"]
        tsp_size = result["tsp_size"]
        key = f"{strategy}_{tsp_size}"

        if key not in convergence_analysis:
            convergence_analysis[key] = {
                "generations_to_best": [],
                "final_improvements": [],
                "convergence_curves": [],
            }

        # Find generation where best cost was achieved
        log = result["log"]
        best_cost = min([entry["cost"] for entry in log])
        gen_to_best = next(
            (entry["generation"] for entry in log if entry["cost"] == best_cost),
            len(log),
        )

        convergence_analysis[key]["generations_to_best"].append(gen_to_best)
        convergence_analysis[key]["final_improvements"].append(result["improvement"])
        convergence_analysis[key]["convergence_curves"].append(
            [entry["best_so_far"] for entry in log]
        )

    return convergence_analysis


def plot_strategy_comparison(results: List[Dict[str, Any]], save_path: str = None):
    """Plot comparison of strategies across TSP sizes"""
    df = create_summary_table(results)

    # Group by strategy and size, calculate statistics
    grouped = df.groupby(["Strategy", "TSP_Size"])["Improvement_%"].agg(
        ["mean", "std", "count"]
    )

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    tsp_sizes = ["small", "medium", "large"]
    strategies = df["Strategy"].unique()

    for i, size in enumerate(tsp_sizes):
        size_data = grouped.xs(size, level="TSP_Size")

        x_pos = np.arange(len(strategies))
        means = [
            size_data.loc[s, "mean"] if s in size_data.index else 0 for s in strategies
        ]
        stds = [
            size_data.loc[s, "std"] if s in size_data.index else 0 for s in strategies
        ]

        bars = axes[i].bar(x_pos, means, yerr=stds, capsize=5, alpha=0.8)
        axes[i].set_title(f"{size.title()} TSP")
        axes[i].set_ylabel("Average Improvement %")
        axes[i].set_xlabel("Strategy")
        axes[i].set_xticks(x_pos)
        axes[i].set_xticklabels(strategies, rotation=45)
        axes[i].grid(True, alpha=0.3)

        # Add value labels on bars
        for bar, mean in zip(bars, means):
            height = bar.get_height()
            axes[i].text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 0.5,
                f"{mean:.1f}%",
                ha="center",
                va="bottom",
            )

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.show()


def plot_convergence_curves(results: List[Dict[str, Any]], save_path: str = None):
    """Plot convergence curves for all strategies"""
    convergence_data = analyze_convergence(results)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    tsp_sizes = ["small", "medium", "large"]
    strategies = ["greedy", "search", "mathematical"]
    colors = ["blue", "red", "green"]

    for i, size in enumerate(tsp_sizes):
        for j, strategy in enumerate(strategies):
            key = f"{strategy}_{size}"
            if key in convergence_data:
                curves = convergence_data[key]["convergence_curves"]

                # Average convergence curve
                if curves:
                    max_length = max(len(curve) for curve in curves)
                    # Pad shorter curves with their final value
                    padded_curves = []
                    for curve in curves:
                        padded = curve + [curve[-1]] * (max_length - len(curve))
                        padded_curves.append(padded)

                    avg_curve = np.mean(padded_curves, axis=0)
                    std_curve = np.std(padded_curves, axis=0)
                    generations = range(1, len(avg_curve) + 1)

                    axes[i].plot(
                        generations,
                        avg_curve,
                        color=colors[j],
                        label=strategy.title(),
                        linewidth=2,
                    )
                    axes[i].fill_between(
                        generations,
                        avg_curve - std_curve,
                        avg_curve + std_curve,
                        color=colors[j],
                        alpha=0.2,
                    )

        axes[i].set_title(f"{size.title()} TSP - Convergence")
        axes[i].set_xlabel("Generation")
        axes[i].set_ylabel("Best Cost So Far")
        axes[i].legend()
        axes[i].grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.show()


def generate_statistical_report(results: List[Dict[str, Any]]) -> str:
    """Generate a statistical analysis report"""
    df = create_summary_table(results)

    report = []
    report.append("=" * 60)
    report.append("PROMPT STRATEGY EXPERIMENT ANALYSIS REPORT")
    report.append("=" * 60)
    report.append("")

    # Overall statistics
    report.append("OVERALL STATISTICS:")
    report.append(f"Total experiments: {len(results)}")
    report.append(f"Strategies tested: {len(df['Strategy'].unique())}")
    report.append(f"TSP sizes tested: {len(df['TSP_Size'].unique())}")
    report.append(
        f"Runs per configuration: {df.groupby(['Strategy', 'TSP_Size']).size().iloc[0]}"
    )
    report.append("")

    # Performance by strategy
    report.append("PERFORMANCE BY STRATEGY:")
    strategy_stats = df.groupby("Strategy")["Improvement_%"].agg(
        ["count", "mean", "std", "min", "max"]
    )
    for strategy in strategy_stats.index:
        stats = strategy_stats.loc[strategy]
        report.append(f"{strategy.title()}:")
        report.append(
            f"  Average improvement: {stats['mean']:.2f}% ± {stats['std']:.2f}%"
        )
        report.append(f"  Best improvement: {stats['max']:.2f}%")
        report.append(f"  Worst improvement: {stats['min']:.2f}%")
        report.append("")

    # Performance by problem size
    report.append("PERFORMANCE BY PROBLEM SIZE:")
    size_stats = df.groupby("TSP_Size")["Improvement_%"].agg(
        ["count", "mean", "std", "min", "max"]
    )
    for size in ["small", "medium", "large"]:
        if size in size_stats.index:
            stats = size_stats.loc[size]
            report.append(f"{size.title()} TSP:")
            report.append(
                f"  Average improvement: {stats['mean']:.2f}% ± {stats['std']:.2f}%"
            )
            report.append(f"  Best improvement: {stats['max']:.2f}%")
            report.append(f"  Worst improvement: {stats['min']:.2f}%")
            report.append("")

    # Best performing combinations
    report.append("BEST PERFORMING COMBINATIONS:")
    best_combos = (
        df.groupby(["Strategy", "TSP_Size"])["Improvement_%"]
        .mean()
        .sort_values(ascending=False)
    )
    for i, ((strategy, size), improvement) in enumerate(best_combos.head(5).items()):
        report.append(
            f"{i + 1}. {strategy.title()} on {size} TSP: {improvement:.2f}% improvement"
        )
    report.append("")

    return "\n".join(report)


def create_comprehensive_analysis(
    results_file: str, output_dir: str = "analysis_output"
):
    """Create comprehensive analysis of experiment results"""
    import os

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Load results
    results = load_experiment_results(results_file)

    # Generate plots
    plot_strategy_comparison(results, save_path=f"{output_dir}/strategy_comparison.png")
    plot_convergence_curves(results, save_path=f"{output_dir}/convergence_curves.png")

    # Generate statistical report
    report = generate_statistical_report(results)
    with open(f"{output_dir}/statistical_report.txt", "w") as f:
        f.write(report)

    # Save summary table
    df = create_summary_table(results)
    df.to_csv(f"{output_dir}/summary_table.csv", index=False)

    print(f"Analysis complete. Results saved to: {output_dir}")
    print("\nStatistical Report:")
    print(report)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        results_file = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "analysis_output"
        create_comprehensive_analysis(results_file, output_dir)
    else:
        print(
            "Usage: python experiment_analysis.py <results_file.json> [output_directory]"
        )
        print(
            "Example: python experiment_analysis.py experiments/results_20240702_120000/final_results.json"
        )
