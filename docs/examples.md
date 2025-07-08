# Examples

This document provides practical examples and tutorials for using Cadence.

## Basic Usage Examples

### Simple TSP Evolution

```python
from src.tasks.tsp_task import TSPTask
from src.database import Database
from src.llm import LLM
from src.evaluator import Evaluator
from src.evolve import apply_diff

# Setup
task = TSPTask(n_cities=10)
db = Database()
llm = LLM()
evaluator = Evaluator(task)

# Initialize with baseline program
program = task.baseline_program
program_id = db.add_program(program, generation=0)

# Evolution loop
for generation in range(1, 51):
    print(f"Generation {generation}")

    # Select parent
    parent = db.get_program(program_id)

    # Generate children
    children = []
    for _ in range(5):
        # Create prompt for LLM
        prompt = f"""
Improve this TSP solution:

```python
{parent['code']}
```

Generate better code for the marked blocks.
Focus on algorithmic improvements.
"""

        # Get LLM response
        response = llm.generate(prompt)
        diffs = extract_code_blocks(response)

        # Apply changes
        child_code = apply_diff(parent['code'], diffs)

        # Evaluate
        result = evaluator.evaluate_program(child_code)

        # Store
        child_id = db.add_program(
            child_code,
            generation=generation,
            parent_id=parent['id'],
            cost=result['cost'],
            feasible=result['feasible']
        )

        children.append({
            'id': child_id,
            'cost': result['cost'],
            'code': child_code
        })

    # Select best child as new parent
    best_child = min(children, key=lambda c: c['cost'])
    program_id = best_child['id']

    print(f"Best cost: {best_child['cost']}")

print("Evolution complete!")
```

### Custom Task Example

```python
# Define a new optimization problem
from src.task import Task
import random
import math

class QuadraticTask(Task):
    """Optimize a quadratic function: minimize f(x) = ax² + bx + c"""

    def __init__(self, a=1, b=0, c=0):
        self.a = a
        self.b = b
        self.c = c

    @property
    def function_name(self):
        return "optimize"

    def generate_inputs(self, seed: int):
        # Return function coefficients
        return {"a": self.a, "b": self.b, "c": self.c}

    def evaluate(self, output, input_data):
        if not isinstance(output, (int, float)):
            return {"cost": float("inf"), "feasible": False}

        x = output
        a, b, c = input_data["a"], input_data["b"], input_data["c"]
        cost = a * x**2 + b * x + c

        return {"cost": cost, "feasible": True}

    @property
    def baseline_program(self):
        return '''
def optimize(coefficients):
    """Find x that minimizes ax² + bx + c"""
    ### START_BLOCK
    # Simple random search
    import random
    best_x = 0
    best_cost = float('inf')

    for _ in range(100):
        x = random.uniform(-10, 10)
        a, b, c = coefficients["a"], coefficients["b"], coefficients["c"]
        cost = a * x**2 + b * x + c

        if cost < best_cost:
            best_x = x
            best_cost = cost

    return best_x
    ### END_BLOCK
'''

# Use the custom task
task = QuadraticTask(a=2, b=-4, c=1)  # Minimum at x=1, f(1)=-1
# Run evolution as before...
```

## Advanced Examples

### Multi-Objective Optimization

```python
class MultiObjectiveTSP(TSPTask):
    """TSP with multiple objectives: distance and tour complexity"""

    def evaluate(self, output, input_data):
        # Get base TSP evaluation
        base_result = super().evaluate(output, input_data)

        if not base_result["feasible"]:
            return base_result

        # Calculate additional objectives
        complexity = self.calculate_complexity(output)
        diversity = self.calculate_diversity(output)

        # Weighted combination
        distance_cost = base_result["cost"]
        total_cost = 0.7 * distance_cost + 0.2 * complexity + 0.1 * diversity

        return {
            "cost": total_cost,
            "feasible": True,
            "objectives": {
                "distance": distance_cost,
                "complexity": complexity,
                "diversity": diversity
            }
        }

    def calculate_complexity(self, tour):
        """Measure tour complexity (number of direction changes)"""
        if len(tour) < 3:
            return 0

        directions = []
        for i in range(len(tour)):
            p1 = tour[i]
            p2 = tour[(i + 1) % len(tour)]
            p3 = tour[(i + 2) % len(tour)]

            # Calculate turn angle
            angle = self.calculate_turn_angle(p1, p2, p3)
            directions.append(angle)

        # Count significant direction changes
        changes = sum(1 for angle in directions if abs(angle) > 0.5)
        return changes / len(tour)  # Normalize

    def calculate_diversity(self, tour):
        """Measure how different this tour is from common patterns"""
        # Simple heuristic: prefer non-sequential patterns
        sequential_count = sum(
            1 for i in range(len(tour) - 1)
            if abs(tour[i] - tour[i + 1]) == 1
        )
        return sequential_count / len(tour)
```

### Adaptive Evolution

```python
class AdaptiveEvolution:
    """Evolution system that adapts parameters based on progress"""

    def __init__(self, task, initial_population_size=20):
        self.task = task
        self.population_size = initial_population_size
        self.mutation_rate = 0.8
        self.stagnation_count = 0
        self.best_cost_history = []

    def evolve(self, generations=100):
        # Initialize population
        population = self.initialize_population()

        for generation in range(generations):
            # Track progress
            current_best = min(p["cost"] for p in population)
            self.best_cost_history.append(current_best)

            # Adapt parameters
            self.adapt_parameters(generation)

            # Evolve generation
            new_population = []

            for _ in range(self.population_size):
                parent = self.select_parent(population)
                child = self.mutate_program(parent)
                new_population.append(child)

            # Combine and select
            combined = population + new_population
            population = self.select_survivors(combined)

            print(f"Gen {generation}: Best={current_best:.3f}, "
                  f"Pop={len(population)}, Mut={self.mutation_rate:.2f}")

        return population

    def adapt_parameters(self, generation):
        """Adapt evolution parameters based on progress"""

        # Check for stagnation
        if len(self.best_cost_history) >= 10:
            recent_improvement = (
                self.best_cost_history[-10] - self.best_cost_history[-1]
            )

            if recent_improvement < 1e-6:
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0

        # Increase mutation rate if stagnating
        if self.stagnation_count > 5:
            self.mutation_rate = min(0.95, self.mutation_rate * 1.2)
            print(f"Increasing mutation rate to {self.mutation_rate:.2f}")

        # Adjust population size based on generation
        if generation < 20:
            # Explore widely early on
            self.population_size = 30
        elif generation < 50:
            # Balance exploration and exploitation
            self.population_size = 20
        else:
            # Focus on exploitation
            self.population_size = 10

        # Dynamic instruction evolution
        if generation % 20 == 0 and generation > 0:
            self.evolve_instructions()

    def evolve_instructions(self):
        """Evolve the instructions given to the LLM"""
        current_best = min(self.best_cost_history[-20:])
        improvement_rate = (
            self.best_cost_history[-20] - current_best
        ) / 20

        meta_prompt = f"""
Current best cost: {current_best:.3f}
Recent improvement rate: {improvement_rate:.6f}
Generation: {len(self.best_cost_history)}

Current instructions: "{self.current_instructions}"

Suggest improved instructions for the LLM to generate better TSP solutions.
Focus on areas where improvement is needed.
"""

        new_instructions = self.llm.generate(meta_prompt)
        self.current_instructions = new_instructions
        print(f"Updated instructions: {new_instructions[:100]}...")
```

### Experiment Comparison

```python
def compare_prompt_strategies():
    """Compare different prompting strategies"""

    strategies = {
        "basic": {
            "instructions": "Improve the TSP solution",
            "temperature": 0.7
        },
        "detailed": {
            "instructions": """
            Improve the TSP solution by:
            1. Reducing total tour distance
            2. Avoiding crossing paths
            3. Using efficient algorithms like nearest neighbor or 2-opt
            4. Handling edge cases properly
            """,
            "temperature": 0.5
        },
        "creative": {
            "instructions": """
            Think creatively about TSP optimization:
            - Try unconventional approaches
            - Combine multiple algorithms
            - Use heuristics and approximations
            - Be innovative but maintain correctness
            """,
            "temperature": 0.9
        }
    }

    results = {}

    for strategy_name, config in strategies.items():
        print(f"\nTesting strategy: {strategy_name}")

        strategy_results = []

        for run in range(10):  # 10 runs per strategy
            print(f"  Run {run + 1}/10")

            # Configure evolution
            evolution = EvolutionSystem(
                task=TSPTask(n_cities=15),
                instructions=config["instructions"],
                llm_temperature=config["temperature"],
                generations=50,
                population_size=20
            )

            # Run evolution
            result = evolution.evolve()
            strategy_results.append({
                "final_cost": result["best_cost"],
                "convergence_generation": result["convergence_generation"],
                "total_time": result["execution_time"]
            })

        results[strategy_name] = strategy_results

    # Analyze results
    for strategy, data in results.items():
        costs = [r["final_cost"] for r in data]
        print(f"\n{strategy.upper()} Strategy:")
        print(f"  Mean cost: {np.mean(costs):.3f} ± {np.std(costs):.3f}")
        print(f"  Best cost: {min(costs):.3f}")
        print(f"  Success rate: {sum(1 for c in costs if c < 500) / len(costs):.1%}")

    return results

# Run comparison
comparison_results = compare_prompt_strategies()
```

### Custom Visualizations

```python
import matplotlib.pyplot as plt
import networkx as nx

def visualize_evolution_tree(database, experiment_id):
    """Create a tree visualization of program evolution"""

    # Get all programs from experiment
    programs = database.get_experiment_programs(experiment_id)

    # Build graph
    G = nx.DiGraph()

    for program in programs:
        G.add_node(program["id"],
                  cost=program["cost"],
                  generation=program["generation"],
                  feasible=program["feasible"])

        if program["parent_id"]:
            G.add_edge(program["parent_id"], program["id"])

    # Layout
    pos = {}
    generation_groups = {}

    for node, data in G.nodes(data=True):
        gen = data["generation"]
        if gen not in generation_groups:
            generation_groups[gen] = []
        generation_groups[gen].append(node)

    # Position nodes by generation
    for gen, nodes in generation_groups.items():
        for i, node in enumerate(nodes):
            pos[node] = (gen, i - len(nodes) / 2)

    # Color by cost
    costs = [G.nodes[node]["cost"] for node in G.nodes()]

    plt.figure(figsize=(15, 10))

    # Draw nodes
    nx.draw_networkx_nodes(G, pos,
                          node_color=costs,
                          node_size=300,
                          cmap=plt.cm.RdYlGn_r,
                          alpha=0.8)

    # Draw edges
    nx.draw_networkx_edges(G, pos,
                          edge_color='gray',
                          arrows=True,
                          alpha=0.5)

    # Add labels for best programs
    best_programs = sorted(programs, key=lambda p: p["cost"])[:5]
    labels = {p["id"]: f"{p['cost']:.1f}" for p in best_programs}
    nx.draw_networkx_labels(G, pos, labels, font_size=8)

    plt.title("Evolution Tree")
    plt.xlabel("Generation")
    plt.ylabel("Population")
    plt.colorbar(plt.cm.ScalarMappable(cmap=plt.cm.RdYlGn_r),
                label="Cost")
    plt.show()

def plot_diversity_evolution(database, experiment_id):
    """Plot how population diversity changes over generations"""

    generations = database.get_generation_stats(experiment_id)

    gen_numbers = [g["generation"] for g in generations]
    diversity_scores = [g["diversity"] for g in generations]
    avg_costs = [g["average_cost"] for g in generations]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Diversity plot
    ax1.plot(gen_numbers, diversity_scores, 'b-', linewidth=2, label='Diversity')
    ax1.set_ylabel('Population Diversity')
    ax1.set_title('Population Diversity Over Time')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Cost plot
    ax2.plot(gen_numbers, avg_costs, 'r-', linewidth=2, label='Average Cost')
    ax2.set_xlabel('Generation')
    ax2.set_ylabel('Average Cost')
    ax2.set_title('Average Cost Over Time')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    plt.show()
```

### Performance Profiling

```python
import time
import cProfile
import pstats
from memory_profiler import profile

class PerformanceProfiler:
    """Profile evolution performance to identify bottlenecks"""

    def __init__(self):
        self.metrics = {}
        self.start_times = {}

    def start_timer(self, operation):
        self.start_times[operation] = time.time()

    def end_timer(self, operation):
        if operation in self.start_times:
            elapsed = time.time() - self.start_times[operation]
            if operation not in self.metrics:
                self.metrics[operation] = []
            self.metrics[operation].append(elapsed)

    def profile_evolution(self, evolution_system, generations=10):
        """Profile a complete evolution run"""

        # CPU profiling
        profiler = cProfile.Profile()
        profiler.enable()

        # Memory profiling wrapper
        @profile
        def run_evolution():
            return evolution_system.evolve(generations)

        # Run with timing
        self.start_timer("total_evolution")
        result = run_evolution()
        self.end_timer("total_evolution")

        profiler.disable()

        # Save CPU profile
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.dump_stats('evolution_profile.prof')

        # Print timing summary
        self.print_timing_summary()

        return result

    def print_timing_summary(self):
        """Print performance summary"""
        print("\nPerformance Summary:")
        print("=" * 50)

        for operation, times in self.metrics.items():
            avg_time = sum(times) / len(times)
            total_time = sum(times)
            print(f"{operation:20s}: {avg_time:.3f}s avg, {total_time:.3f}s total ({len(times)} calls)")

# Usage
profiler = PerformanceProfiler()
evolution = EvolutionSystem(task=TSPTask(n_cities=20))

# Add timing to key operations
class TimedEvolutionSystem(EvolutionSystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profiler = PerformanceProfiler()

    def mutate_program(self, parent):
        self.profiler.start_timer("llm_mutation")
        result = super().mutate_program(parent)
        self.profiler.end_timer("llm_mutation")
        return result

    def evaluate_program(self, program):
        self.profiler.start_timer("program_evaluation")
        result = super().evaluate_program(program)
        self.profiler.end_timer("program_evaluation")
        return result

# Run profiled evolution
timed_evolution = TimedEvolutionSystem(task=TSPTask(n_cities=15))
profiler.profile_evolution(timed_evolution, generations=20)
```

These examples demonstrate various aspects of using Cadence, from basic evolution to advanced techniques like multi-objective optimization, adaptive parameters, and performance profiling. Each example can be adapted for specific use cases and research questions.
