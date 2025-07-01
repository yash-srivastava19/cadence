# analyze_results.py
import numpy as np
import json
import matplotlib.pyplot as plt

RL_FILE = "rl_experiment_log.json"
LLM_FILE = "experiment_log.json"


def load_log(filename=LLM_FILE):
    with open(filename, "r") as f:
        return json.load(f)


def plot_multiple_views(log):
    generations = []
    cost = []
    for entry in log:
        if entry["cost"] < 1000:  # Skip invalid cost values
            generations.append(entry["generation"])
            cost.append(entry["cost"])

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

    # 1. Line plot with moving average
    ax1.plot(generations, cost, alpha=0.3, color="lightblue", label="Raw data")
    if len(cost) > 10:
        window = min(10, len(cost) // 5)
        moving_avg = np.convolve(cost, np.ones(window) / window, mode="valid")
        moving_gen = generations[window - 1 :]
        ax1.plot(
            moving_gen,
            moving_avg,
            color="red",
            linewidth=2,
            label=f"Moving avg ({window})",
        )
    ax1.set_xlabel("Generation")
    ax1.set_ylabel("Cost")
    ax1.set_title("Cost Evolution with Trend")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Histogram of costs
    ax2.hist(cost, bins=30, alpha=0.7, color="skyblue", edgecolor="black")
    ax2.axvline(
        np.mean(cost), color="red", linestyle="--", label=f"Mean: {np.mean(cost):.1f}"
    )
    ax2.axvline(
        np.median(cost),
        color="orange",
        linestyle="--",
        label=f"Median: {np.median(cost):.1f}",
    )
    ax2.set_xlabel("Cost")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Distribution of Costs")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. Box plot by generation ranges
    gen_ranges = np.arange(0, max(generations) + 10, 10)
    box_data = []
    box_labels = []
    for i in range(len(gen_ranges) - 1):
        range_costs = [
            c
            for g, c in zip(generations, cost)
            if gen_ranges[i] <= g < gen_ranges[i + 1]
        ]
        if range_costs:
            box_data.append(range_costs)
            box_labels.append(f"{gen_ranges[i]}-{gen_ranges[i + 1] - 1}")

    ax3.boxplot(box_data, labels=box_labels)
    ax3.set_xlabel("Generation Range")
    ax3.set_ylabel("Cost")
    ax3.set_title("Cost Distribution by Generation Ranges")
    ax3.grid(True, alpha=0.3)
    plt.setp(ax3.get_xticklabels(), rotation=45)

    # 4. Best cost over time (minimum so far)
    best_costs = []
    current_best = float("inf")
    for c in cost:
        if c < current_best:
            current_best = c
        best_costs.append(current_best)

    ax4.plot(
        generations, best_costs, color="green", linewidth=2, marker="o", markersize=3
    )
    ax4.set_xlabel("Generation")
    ax4.set_ylabel("Best Cost So Far")
    ax4.set_title("Best Cost Evolution (Optimization Progress)")
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    # plt.savefig("comprehensive_analysis.png", dpi=300, bbox_inches='tight')
    plt.show()


def plot_simple_trend(log):
    """Simpler trend visualization"""
    generations = []
    cost = []
    for entry in log:
        if entry["cost"] < 1000:
            generations.append(entry["generation"])
            cost.append(entry["cost"])

    plt.figure(figsize=(12, 6))

    # Plot raw data as light points
    plt.scatter(generations, cost, alpha=0.7, s=20, color="lightblue")

    # Add moving average
    if len(cost) > 5:
        window = max(5, len(cost) // 20)
        moving_avg = np.convolve(cost, np.ones(window) / window, mode="valid")
        moving_gen = generations[window - 1 :]
        plt.plot(
            moving_gen,
            moving_avg,
            color="red",
            linewidth=3,
            label=f"Trend (window={window})",
        )

    # Add best-so-far line
    best_costs = []
    current_best = float("inf")
    for c in cost:
        current_best = min(current_best, c)
        best_costs.append(current_best)
    plt.plot(generations, best_costs, color="green", linewidth=2, label="Best so far")

    plt.xlabel("Generation")
    plt.ylabel("Cost")
    plt.title("Cost Evolution with Clear Trends")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    # plt.savefig("simple_trend.png", dpi=300)
    plt.show()


def plot_metric_over_generations(log):
    generations = []
    cost = []
    for i, entry in enumerate(log):
        if entry["cost"] >= 1000:
            continue  # Skip invalid cost values
        else:
            generations.append(entry["generation"])
            cost.append(entry["cost"])

    # for i, cost_value in enumerate(cost):
    #     if cost_value >= 1000:
    #         cost[i] = 0.0
    #         # cost[i] = mean(cost)
    #         # raise ValueError(f"Invalid cost value: {cost_value}. Expected a number.")
    plt.figure(figsize=(12, 6))
    # use the feasibility from the data as whatever points are infeasible, make them red, othere as blue
    # plt.plot(generations, cost, marker="o", linestyle="-", color="royalblue")
    plt.scatter(
        generations,
        cost,
        c=["red" if c == 0.0 else "royalblue" for c in cost],
        label="Cost",
    )
    plt.xlabel("Generation")
    plt.ylabel("Evaluation Cost")
    plt.title("Cost Evolution Over Generations")
    plt.grid(True)
    plt.tight_layout()
    # plt.savefig("cost_evolution.png")
    plt.show()


if __name__ == "__main__":
    log = load_log()
    plot_multiple_views(log)
    # plot_simple_trend(log)
    # plot_metric_over_generations(log)
