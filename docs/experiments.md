# Experiments

Cadence provides a comprehensive framework for running and analyzing evolutionary experiments. This document explains how to design, execute, and analyze experiments.

## Experiment Framework

The experiment system allows you to:
- Run multiple evolution trials with different parameters
- Compare different algorithmic approaches
- Analyze statistical significance of results
- Generate comprehensive reports

## Running Experiments

### Basic Experiment

```python
from experiments.run_experiment import ExperimentRunner
from experiments.experiment_config import ExperimentConfig

# Define experiment configuration
config = ExperimentConfig(
    name="tsp_baseline_study",
    description="Evaluate baseline TSP evolution",
    runs=10,
    generations=100,
    population_size=20
)

# Run experiment
runner = ExperimentRunner(config)
results = runner.run()

# Save results
runner.save_results("results/tsp_baseline/")
```

### Parameter Sweep

```python
# Test different population sizes
population_sizes = [10, 20, 50, 100]
results = []

for pop_size in population_sizes:
    config = ExperimentConfig(
        name=f"pop_size_{pop_size}",
        population_size=pop_size,
        runs=5
    )

    runner = ExperimentRunner(config)
    result = runner.run()
    results.append(result)

# Analyze results
from experiments.analysis import analyze_parameter_sweep
analysis = analyze_parameter_sweep(results, parameter="population_size")
```

### Multi-Condition Experiments

```python
conditions = [
    {
        "name": "conservative",
        "llm_temperature": 0.3,
        "instructions": "Make small, careful improvements"
    },
    {
        "name": "exploratory",
        "llm_temperature": 0.8,
        "instructions": "Try bold, creative approaches"
    },
    {
        "name": "adaptive",
        "llm_temperature": "adaptive",  # Changes during evolution
        "instructions": "Balance exploration and exploitation"
    }
]

for condition in conditions:
    config = ExperimentConfig(
        name=f"strategy_{condition['name']}",
        **condition,
        runs=10
    )

    runner = ExperimentRunner(config)
    runner.run()
```

## Experiment Configuration

### Configuration Files

Create structured experiment definitions:

```json
{
  "experiment": {
    "name": "prompt_strategy_comparison",
    "description": "Compare different prompting strategies for TSP",
    "runs": 20,
    "save_intermediate": true
  },
  "base_config": {
    "task": "tsp",
    "n_cities": 15,
    "generations": 50,
    "population_size": 20
  },
  "conditions": [
    {
      "name": "basic_prompt",
      "instructions": "Improve the TSP solution",
      "llm_temperature": 0.7
    },
    {
      "name": "detailed_prompt",
      "instructions": "Focus on algorithmic efficiency, consider edge cases, and optimize for minimum tour length",
      "llm_temperature": 0.5
    },
    {
      "name": "meta_learning",
      "instructions": "adaptive",
      "meta_evolution": true,
      "llm_temperature": 0.6
    }
  ],
  "analysis": {
    "metrics": ["final_cost", "convergence_generation", "diversity"],
    "statistical_tests": ["mann_whitney_u", "kruskal_wallis"],
    "significance_level": 0.05
  }
}
```

### Dynamic Configuration

```python
def generate_experiment_config(task_type, difficulty_level):
    """Generate experiment configuration based on task and difficulty."""

    base_config = {
        "runs": 10,
        "generations": 100
    }

    if task_type == "tsp":
        if difficulty_level == "easy":
            base_config.update({
                "n_cities": 10,
                "population_size": 15
            })
        elif difficulty_level == "hard":
            base_config.update({
                "n_cities": 30,
                "population_size": 50,
                "generations": 200
            })

    return ExperimentConfig(**base_config)
```

## Experiment Execution

### Serial Execution

```python
class ExperimentRunner:
    def __init__(self, config):
        self.config = config
        self.results = []

    def run(self):
        """Run all experiment trials."""
        for run_id in range(self.config.runs):
            print(f"Running trial {run_id + 1}/{self.config.runs}")

            # Initialize evolution system
            evolution = EvolutionSystem(self.config)

            # Run evolution
            result = evolution.evolve()

            # Store results
            self.results.append({
                "run_id": run_id,
                "config": self.config.to_dict(),
                "result": result,
                "timestamp": datetime.now()
            })

            # Save intermediate results
            if self.config.save_intermediate:
                self.save_intermediate_result(run_id, result)

        return self.results
```

### Parallel Execution

```python
from multiprocessing import Pool
from concurrent.futures import ProcessPoolExecutor

class ParallelExperimentRunner:
    def __init__(self, config, max_workers=4):
        self.config = config
        self.max_workers = max_workers

    def run_single_trial(self, run_id):
        """Run a single experiment trial."""
        evolution = EvolutionSystem(self.config)
        result = evolution.evolve()
        return {
            "run_id": run_id,
            "result": result,
            "timestamp": datetime.now()
        }

    def run(self):
        """Run experiments in parallel."""
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.run_single_trial, run_id)
                for run_id in range(self.config.runs)
            ]

            results = []
            for future in futures:
                try:
                    result = future.result(timeout=3600)  # 1 hour timeout
                    results.append(result)
                except Exception as e:
                    print(f"Trial failed: {e}")

            return results
```

### Distributed Execution

```python
# Using Ray for distributed experiments
import ray

@ray.remote
def run_experiment_trial(config, run_id):
    """Remote function to run experiment trial."""
    evolution = EvolutionSystem(config)
    return evolution.evolve()

class DistributedExperimentRunner:
    def __init__(self, config):
        self.config = config
        ray.init()

    def run(self):
        """Run experiments across multiple machines."""
        futures = [
            run_experiment_trial.remote(self.config, run_id)
            for run_id in range(self.config.runs)
        ]

        results = ray.get(futures)
        ray.shutdown()

        return results
```

## Data Collection

### Metrics Collection

```python
class MetricsCollector:
    def __init__(self):
        self.metrics = defaultdict(list)

    def collect_generation_metrics(self, generation, population):
        """Collect metrics for a generation."""
        costs = [p["cost"] for p in population]

        self.metrics["generation"].append(generation)
        self.metrics["best_cost"].append(min(costs))
        self.metrics["average_cost"].append(sum(costs) / len(costs))
        self.metrics["worst_cost"].append(max(costs))
        self.metrics["diversity"].append(calculate_diversity(population))
        self.metrics["feasible_solutions"].append(
            sum(1 for p in population if p["feasible"])
        )

    def collect_final_metrics(self, result):
        """Collect final experiment metrics."""
        return {
            "final_best_cost": result["best_cost"],
            "convergence_generation": result["convergence_generation"],
            "total_evaluations": result["total_evaluations"],
            "llm_calls": result["llm_calls"],
            "execution_time": result["execution_time"]
        }
```

### Real-time Monitoring

```python
class ExperimentMonitor:
    def __init__(self, experiment_name):
        self.experiment_name = experiment_name
        self.start_time = time.time()

    def log_progress(self, run_id, generation, best_cost):
        """Log experiment progress."""
        elapsed = time.time() - self.start_time

        log_data = {
            "experiment": self.experiment_name,
            "run": run_id,
            "generation": generation,
            "best_cost": best_cost,
            "elapsed_time": elapsed,
            "timestamp": datetime.now().isoformat()
        }

        # Log to file
        with open(f"logs/{self.experiment_name}.jsonl", "a") as f:
            f.write(json.dumps(log_data) + "\n")

        # Send to monitoring system (optional)
        if self.monitoring_enabled:
            self.send_to_monitoring(log_data)
```

## Statistical Analysis

### Comparative Analysis

```python
from scipy import stats
import numpy as np

class ExperimentAnalysis:
    def __init__(self, results):
        self.results = results

    def compare_conditions(self, metric="final_cost"):
        """Compare multiple experimental conditions."""
        conditions = {}

        for result in self.results:
            condition = result["condition"]
            value = result[metric]

            if condition not in conditions:
                conditions[condition] = []
            conditions[condition].append(value)

        # Statistical tests
        if len(conditions) == 2:
            return self.two_sample_test(conditions, metric)
        else:
            return self.multi_sample_test(conditions, metric)

    def two_sample_test(self, conditions, metric):
        """Perform two-sample statistical test."""
        cond_names = list(conditions.keys())
        sample1 = conditions[cond_names[0]]
        sample2 = conditions[cond_names[1]]

        # Mann-Whitney U test (non-parametric)
        statistic, p_value = stats.mannwhitneyu(sample1, sample2)

        return {
            "test": "Mann-Whitney U",
            "statistic": statistic,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "effect_size": self.calculate_effect_size(sample1, sample2)
        }

    def multi_sample_test(self, conditions, metric):
        """Perform multi-sample statistical test."""
        samples = list(conditions.values())

        # Kruskal-Wallis test
        statistic, p_value = stats.kruskal(*samples)

        result = {
            "test": "Kruskal-Wallis",
            "statistic": statistic,
            "p_value": p_value,
            "significant": p_value < 0.05
        }

        # Post-hoc pairwise comparisons if significant
        if p_value < 0.05:
            result["pairwise"] = self.pairwise_comparisons(conditions)

        return result
```

### Performance Analysis

```python
def analyze_convergence(experiment_results):
    """Analyze convergence patterns across experiments."""
    convergence_data = []

    for result in experiment_results:
        generations = result["generations"]
        costs = result["best_costs"]

        # Find convergence point
        convergence_gen = find_convergence_point(costs)

        convergence_data.append({
            "run_id": result["run_id"],
            "convergence_generation": convergence_gen,
            "final_cost": costs[-1],
            "improvement_rate": calculate_improvement_rate(costs)
        })

    return {
        "mean_convergence": np.mean([d["convergence_generation"] for d in convergence_data]),
        "convergence_std": np.std([d["convergence_generation"] for d in convergence_data]),
        "success_rate": sum(1 for d in convergence_data if d["convergence_generation"] < len(costs)) / len(convergence_data)
    }

def find_convergence_point(costs, patience=10, tolerance=1e-6):
    """Find the generation where evolution converged."""
    for i in range(patience, len(costs)):
        window = costs[i-patience:i]
        if max(window) - min(window) < tolerance:
            return i - patience
    return len(costs)  # Never converged
```

## Visualization

### Progress Visualization

```python
import matplotlib.pyplot as plt
import seaborn as sns

def plot_evolution_progress(results):
    """Plot evolution progress for multiple runs."""
    plt.figure(figsize=(12, 8))

    for i, result in enumerate(results):
        generations = range(len(result["best_costs"]))
        plt.plot(generations, result["best_costs"],
                alpha=0.3, color='blue', linewidth=1)

    # Plot mean and confidence intervals
    mean_costs = np.mean([r["best_costs"] for r in results], axis=0)
    std_costs = np.std([r["best_costs"] for r in results], axis=0)

    generations = range(len(mean_costs))
    plt.plot(generations, mean_costs, color='red', linewidth=2, label='Mean')
    plt.fill_between(generations,
                     mean_costs - std_costs,
                     mean_costs + std_costs,
                     alpha=0.2, color='red', label='±1 std')

    plt.xlabel('Generation')
    plt.ylabel('Best Cost')
    plt.title('Evolution Progress')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

def plot_condition_comparison(results_by_condition):
    """Compare different experimental conditions."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    # Box plot of final costs
    conditions = list(results_by_condition.keys())
    final_costs = [
        [r["best_costs"][-1] for r in results_by_condition[cond]]
        for cond in conditions
    ]

    axes[0].boxplot(final_costs, labels=conditions)
    axes[0].set_title('Final Cost Distribution')
    axes[0].set_ylabel('Cost')

    # Convergence comparison
    for cond, results in results_by_condition.items():
        mean_costs = np.mean([r["best_costs"] for r in results], axis=0)
        axes[1].plot(mean_costs, label=cond, linewidth=2)

    axes[1].set_xlabel('Generation')
    axes[1].set_ylabel('Mean Best Cost')
    axes[1].set_title('Convergence Comparison')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()
```

## Report Generation

### Automated Reports

```python
class ExperimentReporter:
    def __init__(self, experiment_results):
        self.results = experiment_results
        self.analysis = ExperimentAnalysis(experiment_results)

    def generate_report(self, output_path):
        """Generate comprehensive experiment report."""
        report = {
            "experiment_info": self.get_experiment_info(),
            "summary_statistics": self.get_summary_statistics(),
            "statistical_analysis": self.get_statistical_analysis(),
            "visualizations": self.generate_visualizations(),
            "conclusions": self.generate_conclusions()
        }

        # Save as JSON
        with open(f"{output_path}/report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Generate HTML report
        self.generate_html_report(report, output_path)

        return report

    def generate_html_report(self, report, output_path):
        """Generate HTML report with embedded visualizations."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cadence Experiment Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .section { margin: 30px 0; }
                .metric { display: inline-block; margin: 10px; padding: 10px;
                         background: #f0f0f0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>Experiment Report: {experiment_name}</h1>

            <div class="section">
                <h2>Summary</h2>
                <p>{description}</p>
                <div class="metric">Runs: {runs}</div>
                <div class="metric">Best Cost: {best_cost:.3f}</div>
                <div class="metric">Success Rate: {success_rate:.1%}</div>
            </div>

            <div class="section">
                <h2>Statistical Analysis</h2>
                {statistical_results}
            </div>

            <div class="section">
                <h2>Visualizations</h2>
                {visualizations}
            </div>
        </body>
        </html>
        """

        html_content = html_template.format(**report["experiment_info"])

        with open(f"{output_path}/report.html", "w") as f:
            f.write(html_content)
```

## Best Practices

### Experiment Design

1. **Control Variables**: Keep all parameters constant except the one being tested
2. **Sufficient Runs**: Use enough runs for statistical significance (typically 20-30)
3. **Random Seeds**: Use different random seeds for each run
4. **Baseline Comparison**: Always include a baseline condition

### Data Management

1. **Version Control**: Track experiment configurations and code versions
2. **Reproducibility**: Save complete environment and configuration
3. **Metadata**: Record all relevant experimental conditions
4. **Backup**: Store results in multiple locations

### Analysis Guidelines

1. **Statistical Rigor**: Use appropriate statistical tests
2. **Effect Size**: Report practical significance, not just statistical
3. **Multiple Comparisons**: Adjust p-values when testing multiple hypotheses
4. **Visualization**: Always visualize data before statistical analysis
