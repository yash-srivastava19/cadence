# Prompt Strategy Experiments

This directory contains experiments designed to test different prompt engineering strategies for evolutionary algorithm development, specifically focused on the Traveling Salesman Problem (TSP).

## Overview

The experiment tests three different prompt strategies across multiple TSP problem sizes to determine:
1. Which prompt engineering approaches are most effective
2. How strategies scale with problem complexity
3. What algorithmic patterns emerge from different prompting approaches

## Files

### Core Experiment Files
- `prompt_strategy_experiment.py` - Main experiment runner class
- `experiment_config.py` - Configuration and parameter definitions
- `experiment_analysis.py` - Analysis and visualization tools
- `run_experiment.py` - Command-line interface to run complete experiments

### Usage

#### Running a Complete Experiment
```bash
# Run with default configuration
python run_experiment.py

# Run with custom configuration
python run_experiment.py --config my_config.json

# Validate configuration without running
python run_experiment.py --dry-run
```

#### Analyzing Existing Results
```bash
# Analyze existing results
python run_experiment.py --analysis-only path/to/results.json

# Or use analysis module directly
python experiment_analysis.py results.json output_directory
```

## Experiment Design

### Prompt Strategies Tested

1. **Greedy Strategy**
   - Focus on nearest neighbor and greedy heuristics
   - Expected to work well on smaller problems
   - Should converge quickly but may get stuck in local optima

2. **Search Strategy**
   - Emphasizes local search and iterative improvement
   - Expected to perform well on medium-sized problems
   - Should find better solutions through optimization

3. **Mathematical Strategy**
   - Uses graph theory and formal optimization concepts
   - Expected to scale best to larger problems
   - Should discover more sophisticated algorithmic patterns

### Problem Sizes

- **Small TSP**: 8 cities (quick validation, clear patterns)
- **Medium TSP**: 20 cities (realistic complexity)
- **Large TSP**: 40 cities (scalability test)

### Metrics Collected

- **Solution Quality**: Final tour cost
- **Convergence Speed**: Generations to reach best solution
- **Consistency**: Performance across multiple runs
- **Algorithmic Patterns**: Code analysis of evolved solutions

## Expected Results

### Hypotheses

1. **H1**: Different prompt strategies will show significantly different performance
2. **H2**: Strategy effectiveness will vary with problem size
3. **H3**: Different strategies will converge at different rates

### Predictions

- Greedy strategies will converge faster but to worse solutions
- Search-based prompts will outperform greedy on larger problems
- Mathematical prompts will scale best to complex problems

## Output Structure

```
experiments/
├── results_YYYYMMDD_HHMMSS/
│   ├── experiment_config.json     # Configuration used
│   ├── experiment_summary.md      # Human-readable summary
│   ├── final_results.json         # Raw experimental data
│   ├── intermediate_results.json  # Checkpointed results
│   ├── experiment.log             # Detailed logs
│   └── analysis/
│       ├── statistical_report.txt    # Statistical analysis
│       ├── summary_table.csv         # Tabular results
│       ├── strategy_comparison.png   # Performance comparison
│       └── convergence_curves.png    # Convergence analysis
```

## Configuration

The experiment can be customized by modifying `experiment_config.py` or providing a custom JSON configuration file. Key parameters:

```json
{
  "tsp_sizes": {"small": 8, "medium": 20, "large": 40},
  "experiment_params": {
    "runs_per_config": 3,
    "generations_per_run": 10
  }
}
```

## Analysis Features

The analysis module provides:

- **Statistical summaries** with confidence intervals
- **Performance comparisons** across strategies and problem sizes
- **Convergence analysis** showing optimization progress
- **Automated report generation** with key findings

## Real-World Value

This experiment provides concrete evidence about:
- **Prompt Engineering Best Practices**: Which approaches work best for optimization problems
- **Scalability Insights**: How different strategies handle increasing complexity
- **AI Code Generation**: Whether LLMs can discover and apply known algorithmic patterns

## Dependencies

- Python 3.8+
- matplotlib, numpy, pandas (for analysis)
- Parent cadence modules (database, evaluator, llm, etc.)

## Notes

- Each experiment combination runs multiple times for statistical significance
- Results are automatically saved and can be re-analyzed later
- The experiment is designed to be reproducible and extensible
- Analysis includes both statistical tests and visualizations

## Future Extensions

Potential extensions to this experimental framework:
- Additional prompt strategies (e.g., cooperative, competitive)
- Different optimization problems (vehicle routing, scheduling)
- Transfer learning between problem types
- Human vs AI solution comparison
