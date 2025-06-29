# analyze_results.py

import json
import matplotlib.pyplot as plt

RL_FILE = "rl_experiment_log.json"
LLM_FILE = "experiment_log.json"


def load_log(filename=LLM_FILE):
    with open(filename, "r") as f:
        return json.load(f)


def plot_metric_over_generations(log):
    generations = [entry["generation"] for entry in log]
    if RL_FILE:
        cost = [entry["cost"] for entry in log]
    elif LLM_FILE:
        cost = [entry["cost"] for entry in log]

    for i, cost_value in enumerate(cost):
        if cost_value >= 1000:
            cost[i] = 0.0
            # cost[i] = mean(cost)
            # raise ValueError(f"Invalid cost value: {cost_value}. Expected a number.")
    plt.figure(figsize=(10, 6))
    # use the feasibility from the data as whatever points are infeasible, make them red, othere as blue
    plt.plot(generations, cost, marker="o", linestyle="-", color="royalblue")
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
    plt.savefig("cost_evolution.png")
    plt.show()


if __name__ == "__main__":
    log = load_log()
    plot_metric_over_generations(log)
