# Cadence: Evolutionary Programming with Large Language Models

Cadence is a framework for evolving programs using Large Language Models (LLMs) as the mutation operator. The system iteratively generates, evaluates, and improves code solutions through an evolutionary process, currently focused on optimization problems like the Traveling Salesman Problem (TSP).

## What is Cadence?

Cadence implements a novel approach to automated program synthesis and optimization by combining:

- **Evolutionary Algorithms**: Population-based search with selection, mutation, and fitness evaluation
- **Large Language Models**: Code generation and modification capabilities
- **Structured Code Evolution**: Block-based mutations within well-defined program templates
- **Empirical Evaluation**: Performance-driven selection using actual program execution

## Key Features

- **LLM-Driven Evolution**: Uses language models to generate program variations rather than traditional genetic operators
- **Block-Based Mutations**: Structured approach to code modification using marked regions
- **Multi-Objective Optimization**: Balances solution quality with code complexity and execution time
- **Extensible Task Framework**: Abstract base classes allow easy addition of new optimization problems
- **Comprehensive Logging**: SQLite-based storage of evolution history and performance metrics
- **Web Interface**: Real-time visualization of the evolutionary process
- **Deterministic Evaluation**: Reproducible results using fixed random seeds

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Task Layer    │    │  Evolution      │    │   Evaluation    │
│                 │    │   Engine        │    │    System       │
│ • TSPTask       │◄──►│                 │◄──►│                 │
│ • Custom Tasks  │    │ • Prompting     │    │ • Fitness       │
│                 │    │ • LLM Interface │    │ • Validation    │
└─────────────────┘    │ • Diff Apply    │    │ • Metrics       │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Database     │    │   Web UI        │    │   Experiment    │
│                 │    │                 │    │   Framework     │
│ • Programs      │◄──►│ • Visualization │◄──►│                 │
│ • Generations   │    │ • Monitoring    │    │ • A/B Testing   │
│ • Performance   │    │ • Controls      │    │ • Analysis      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

```bash
# Clone and setup
git clone https://github.com/yash-srivastava19/cadence
cd cadence
uv sync

# Configure API keys
export GOOGLE_API_KEY="your-key-here"

# Run evolution
python main.py

# Launch web interface
python ui/launch_ui.py
```

## Documentation Structure

- **[Getting Started](getting-started.md)**: Installation, setup, and first steps
- **[Architecture](architecture.md)**: System design and component overview
- **[API Reference](api/index.md)**: Detailed module and class documentation
- **[Tasks](tasks.md)**: Creating custom optimization problems
- **[Evolution](evolution.md)**: Understanding the evolutionary process
- **[Configuration](configuration.md)**: System settings and parameters
- **[Experiments](experiments.md)**: Running and analyzing experiments
- **[Web Interface](web-interface.md)**: Using the visualization dashboard
- **[Examples](examples.md)**: Code samples and tutorials
- **[Contributing](contributing.md)**: Development guidelines and contribution process

## Research Background

Cadence is inspired by research in:

- **Automated Program Synthesis**: Generating programs from specifications
- **Genetic Programming**: Evolutionary computation for program evolution
- **Large Language Models for Code**: Leveraging LLMs for software engineering tasks
- **Meta-Learning**: Learning to improve the learning process itself

The system addresses limitations of traditional genetic programming by using LLMs' understanding of code semantics and programming patterns to generate more meaningful mutations.

## Use Cases

- **Algorithm Optimization**: Evolving efficient solutions to computational problems
- **Code Generation**: Automated creation of program variants
- **Research Tool**: Studying LLM capabilities in program synthesis
- **Educational Platform**: Understanding evolutionary computation and AI-assisted programming

## License

MIT License - see [LICENSE](../LICENSE) for details.
