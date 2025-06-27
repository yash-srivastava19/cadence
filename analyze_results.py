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

    plt.figure(figsize=(10, 6))
    plt.plot(generations, cost, marker="o", linestyle="-", color="royalblue")
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
