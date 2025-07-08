# Evolution Process

This document explains how Cadence evolves programs using Large Language Models as mutation operators.

## Overview

Cadence implements an evolutionary algorithm where:
- **Population**: Collection of program variants
- **Parents**: Selected programs for generating offspring
- **Mutation**: LLM-generated code modifications
- **Selection**: Performance-based survival of programs
- **Fitness**: Objective function evaluation

## Evolution Loop

The core evolution process follows these steps:

### 1. Initialization

```python
# Create initial population
population = []
for i in range(population_size):
    program = task.baseline_program
    cost = evaluate_program(program)
    population.append({
        "code": program,
        "cost": cost,
        "generation": 0,
        "id": i
    })
```

### 2. Parent Selection

Programs are selected for mutation based on performance:

```python
def select_parent(population, method="tournament"):
    if method == "tournament":
        # Tournament selection
        candidates = random.sample(population, k=3)
        return min(candidates, key=lambda p: p["cost"])

    elif method == "roulette":
        # Fitness-proportionate selection
        weights = [1.0 / (1.0 + p["cost"]) for p in population]
        return random.choices(population, weights=weights)[0]
```

### 3. Prompt Generation

Create evolution prompt for the LLM:

```python
def generate_evolution_prompt(parent, children, instructions):
    prompt = f"""
Task: Improve the following program for {task.function_name}

Parent Program:
```python
{parent["code"]}
```

Previous Children (for reference):
{format_children(children)}

Instructions: {instructions}

Generate improved code for the marked blocks.
"""
    return prompt
```

### 4. LLM Mutation

The LLM generates code modifications:

```python
def mutate_program(parent_code, llm, prompt):
    # Get LLM response
    response = llm.generate(prompt)

    # Extract code diffs
    diffs = parse_code_blocks(response)

    # Apply diffs to parent
    child_code = apply_diff(parent_code, diffs)

    return child_code
```

### 5. Evaluation

Assess the generated program:

```python
def evaluate_program(code, task, num_seeds=5):
    results = []

    for seed in range(num_seeds):
        try:
            # Generate test input
            input_data = task.generate_inputs(seed)

            # Execute program
            func = extract_function(code, task.function_name)
            output = func(input_data)

            # Evaluate result
            result = task.evaluate(output, input_data)
            results.append(result)

        except Exception as e:
            results.append({
                "cost": float("inf"),
                "feasible": False,
                "error": str(e)
            })

    # Aggregate results
    avg_cost = sum(r["cost"] for r in results) / len(results)
    feasible = all(r["feasible"] for r in results)

    return {
        "cost": avg_cost,
        "feasible": feasible,
        "individual_results": results
    }
```

### 6. Population Update

Integrate successful mutations:

```python
def update_population(population, new_program, generation):
    # Add new program
    new_program["generation"] = generation
    population.append(new_program)

    # Remove worst performers if population too large
    if len(population) > max_population_size:
        population.sort(key=lambda p: p["cost"])
        population = population[:max_population_size]

    return population
```

## Selection Strategies

### Tournament Selection

```python
def tournament_selection(population, tournament_size=3):
    """Select parent via tournament selection."""
    candidates = random.sample(population, k=tournament_size)
    return min(candidates, key=lambda p: p["cost"])
```

### Elitism

```python
def elitist_selection(population, elite_size=2):
    """Preserve best performers across generations."""
    population.sort(key=lambda p: p["cost"])
    return population[:elite_size]
```

### Diversity-Based Selection

```python
def diversity_selection(population, parent):
    """Select diverse parents to avoid local optima."""
    distances = []
    for candidate in population:
        # Calculate code similarity
        similarity = compute_code_similarity(parent["code"], candidate["code"])
        distances.append((candidate, 1.0 - similarity))

    # Select based on diversity and performance
    weights = [d[1] * (1.0 / (1.0 + d[0]["cost"])) for d in distances]
    return random.choices([d[0] for d in distances], weights=weights)[0]
```

## Mutation Strategies

### Block-Based Mutation

The primary mutation strategy targets marked code blocks:

```python
# Original code
def tsp(cities):
    ### START_BLOCK
    n = len(cities)
    return list(range(n))
    ### END_BLOCK

# After mutation
def tsp(cities):
    ### START_BLOCK
    n = len(cities)
    best_tour = None
    best_dist = float('inf')

    for start in range(n):
        tour = nearest_neighbor(cities, start)
        dist = calculate_total_distance(tour, cities)
        if dist < best_dist:
            best_tour = tour
            best_dist = dist

    return best_tour
    ### END_BLOCK
```

### Instruction Evolution

Instructions to the LLM can also evolve:

```python
def evolve_instructions(current_instructions, generation, best_cost):
    if generation % 10 == 0:  # Every 10 generations
        meta_prompt = f"""
Current instructions: {current_instructions}
Best cost achieved: {best_cost}
Generation: {generation}

Suggest improved instructions for evolving TSP solutions.
Focus on: algorithmic improvements, efficiency, edge cases.
"""
        new_instructions = llm.generate(meta_prompt)
        return new_instructions
    return current_instructions
```

## Fitness Evaluation

### Multi-Objective Fitness

```python
def calculate_fitness(program, task):
    # Primary objective
    cost = evaluate_program_cost(program, task)

    # Secondary objectives
    complexity = calculate_code_complexity(program["code"])
    execution_time = measure_execution_time(program, task)

    # Weighted combination
    fitness = {
        "cost": cost,
        "complexity": complexity,
        "execution_time": execution_time,
        "combined": 0.7 * cost + 0.2 * complexity + 0.1 * execution_time
    }

    return fitness
```

### Constraint Handling

```python
def evaluate_with_constraints(program, task):
    result = task.evaluate(program["output"], program["input"])

    # Apply constraint penalties
    if not result["feasible"]:
        result["cost"] = float("inf")

    # Time constraint
    if program["execution_time"] > MAX_EXECUTION_TIME:
        result["cost"] *= 1.5  # Penalty for slow solutions

    # Complexity constraint
    if calculate_complexity(program["code"]) > MAX_COMPLEXITY:
        result["cost"] *= 1.2  # Penalty for complex solutions

    return result
```

## Advanced Techniques

### Island Model

Run multiple parallel populations:

```python
def island_evolution(num_islands=4, migration_rate=0.1):
    islands = [initialize_population() for _ in range(num_islands)]

    for generation in range(max_generations):
        # Evolve each island
        for island in islands:
            evolve_generation(island)

        # Migration between islands
        if generation % 10 == 0:
            migrate_individuals(islands, migration_rate)

    # Combine final populations
    final_population = []
    for island in islands:
        final_population.extend(island)

    return final_population
```

### Adaptive Parameters

Adjust evolution parameters based on progress:

```python
def adaptive_parameters(generation, stagnation_count):
    # Increase mutation rate if stagnating
    if stagnation_count > 5:
        mutation_rate = min(0.9, base_mutation_rate * 1.5)
    else:
        mutation_rate = base_mutation_rate

    # Adjust population size
    if generation < 20:
        population_size = 20  # Explore widely early
    else:
        population_size = 10  # Focus on best later

    return {
        "mutation_rate": mutation_rate,
        "population_size": population_size
    }
```

### Novelty Search

Encourage exploration of diverse solutions:

```python
def novelty_score(program, archive):
    distances = []
    for archived_program in archive:
        # Calculate behavioral distance
        behavior_dist = calculate_behavior_distance(
            program["behavior"],
            archived_program["behavior"]
        )
        distances.append(behavior_dist)

    # Novelty = average distance to k nearest neighbors
    distances.sort()
    k = min(5, len(distances))
    novelty = sum(distances[:k]) / k

    return novelty

def behavior_distance(behavior1, behavior2):
    # Compare program behaviors across test cases
    return sum(abs(b1 - b2) for b1, b2 in zip(behavior1, behavior2))
```

## Monitoring Evolution

### Progress Tracking

```python
def track_evolution_progress(population, generation):
    best_cost = min(p["cost"] for p in population)
    avg_cost = sum(p["cost"] for p in population) / len(population)
    diversity = calculate_population_diversity(population)

    metrics = {
        "generation": generation,
        "best_cost": best_cost,
        "average_cost": avg_cost,
        "diversity": diversity,
        "population_size": len(population)
    }

    log_metrics(metrics)
    return metrics
```

### Convergence Detection

```python
def check_convergence(history, patience=10, tolerance=1e-6):
    if len(history) < patience:
        return False

    recent_best = [h["best_cost"] for h in history[-patience:]]
    improvement = recent_best[0] - recent_best[-1]

    return improvement < tolerance
```

## Configuration

### Evolution Parameters

```python
EVOLUTION_CONFIG = {
    "population_size": 20,
    "generations": 100,
    "tournament_size": 3,
    "elite_size": 2,
    "mutation_rate": 0.8,
    "migration_rate": 0.1,
    "stagnation_threshold": 10
}
```

### LLM Parameters

```python
LLM_CONFIG = {
    "temperature": 0.7,
    "max_tokens": 2048,
    "top_p": 0.9,
    "frequency_penalty": 0.1
}
```
