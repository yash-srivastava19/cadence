# Architecture

This document describes the high-level architecture and design principles of Cadence.

## System Overview

Cadence implements an evolutionary algorithm where Large Language Models serve as the mutation operator. The system consists of several key components that work together to evolve programs over generations.

## Core Components

### Task Layer

The task layer defines the optimization problems that Cadence can solve.

```python
# Abstract base class
class Task(ABC):
    @property
    @abstractmethod
    def function_name(self) -> str: ...

    @abstractmethod
    def generate_inputs(self, seed: int): ...

    @abstractmethod
    def evaluate(self, output, input_data) -> float: ...

    @property
    @abstractmethod
    def baseline_program(self) -> str: ...
```

**Key Features:**
- Abstract interface for defining new optimization problems
- Deterministic input generation using seeds
- Flexible evaluation metrics
- Template-based program structure

### Evolution Engine

The evolution engine orchestrates the evolutionary process.

**Components:**
- **Population Management**: Maintains and tracks program populations
- **Selection**: Chooses parent programs for mutation
- **Mutation**: Uses LLM to generate program variants
- **Evaluation**: Assesses program fitness

**Evolution Loop:**
1. Select parent program from population
2. Generate children using LLM mutations
3. Evaluate children on test cases
4. Update population with successful variants
5. Repeat for specified generations

### LLM Interface

Abstracts interaction with Large Language Models.

```python
class LLM:
    def generate(self, prompt: str) -> str:
        """Generate text completion from prompt."""

    def generate_diffs(self, parent_code: str, children_code: List[str],
                      instructions: str) -> List[str]:
        """Generate code diffs for program evolution."""
```

**Features:**
- Provider abstraction (currently Google Gemini)
- Prompt engineering for code generation
- Error handling and retry logic
- Token usage tracking

### Database Layer

Persistent storage for evolution history and analysis.

**Schema:**
- **programs**: Stores program code and metadata
- **generations**: Tracks evolution progress
- **evaluations**: Records performance metrics
- **experiments**: Groups related evolution runs

**Operations:**
- Add/retrieve programs and their performance
- Query evolution history
- Export data for analysis

### Evaluation System

Executes and evaluates generated programs.

**Components:**
- **Code Execution**: Safe execution of generated code
- **Fitness Calculation**: Computes program quality metrics
- **Validation**: Ensures program correctness
- **Performance Tracking**: Measures execution time and resource usage

## Data Flow

```
Input Problem → Task Definition → Initial Population
       ↓
Evolution Loop:
├── Select Parents
├── Generate Prompts
├── LLM Mutation → New Programs
├── Code Execution → Results
├── Fitness Evaluation → Scores
└── Population Update
       ↓
Final Population → Analysis → Results
```

## Design Principles

### Modularity

Each component has clear responsibilities and interfaces:
- Tasks define problems independently
- LLM interface abstracts model details
- Database provides persistent storage
- Evolution engine coordinates the process

### Extensibility

The system supports easy extension:
- New tasks via Task interface
- New LLM providers via LLM interface
- Custom evaluation metrics
- Additional analysis tools

### Reproducibility

Deterministic behavior through:
- Fixed random seeds for input generation
- Consistent prompt formatting
- Versioned program storage
- Comprehensive logging

### Robustness

Error handling and recovery:
- LLM API failures and retries
- Invalid code generation handling
- Database transaction safety
- Graceful degradation

## Code Organization

```
src/
├── task.py              # Abstract task interface
├── evolve.py            # Evolution algorithms
├── llm.py               # LLM interface
├── database.py          # Data persistence
├── evaluator.py         # Program evaluation
├── prompt_sampler.py    # Prompt generation
└── tasks/
    └── tsp_task.py      # TSP implementation

ui/
├── app.py               # Web interface
├── templates/           # HTML templates
└── static/              # CSS/JS assets

experiments/
├── experiment_config.py # Experiment definitions
├── run_experiment.py    # Experiment runner
└── analysis/            # Result analysis

tests/
├── unit/                # Unit tests
├── integration/         # Integration tests
└── fixtures/            # Test data
```

## Configuration System

Configuration is managed through multiple layers:

1. **Default Values**: Hardcoded in classes
2. **Configuration Files**: JSON/YAML for complex setups
3. **Environment Variables**: API keys and runtime settings
4. **Command Line**: Override parameters for runs

Example configuration hierarchy:
```python
# Default
config = {"population_size": 10}

# From file
config.update(load_config("config.json"))

# From environment
config["api_key"] = os.getenv("GEMINI_API_KEY")

# From CLI
config.update(parse_args())
```

## Performance Considerations

### Parallel Evaluation

Programs are evaluated in parallel to improve throughput:
- Process pool for CPU-bound evaluation
- Batch processing for multiple test cases
- Resource limiting to prevent system overload

### Caching

Various caching strategies reduce redundant work:
- LLM response caching for identical prompts
- Program evaluation caching for repeated code
- Database query result caching

### Memory Management

Large populations and long runs require careful memory management:
- Lazy loading of program history
- Periodic garbage collection
- Streaming results for large datasets

## Security Considerations

### Code Execution

Generated code is executed in controlled environments:
- Resource limits (CPU, memory, time)
- Restricted imports and system calls
- Sandboxed execution contexts

### API Security

LLM API interactions follow security best practices:
- API key rotation
- Request rate limiting
- Input sanitization

## Monitoring and Observability

### Logging

Comprehensive logging across all components:
- Structured logging with JSON format
- Multiple log levels (DEBUG, INFO, WARN, ERROR)
- Log rotation and archival

### Metrics

Key metrics tracked during evolution:
- Generation progress and timing
- LLM API usage and costs
- Program evaluation success rates
- Database performance

### Health Checks

System health monitoring:
- LLM API connectivity
- Database availability
- Resource utilization
- Error rates

## Integration Points

### External APIs

- **LLM Providers**: Google Gemini, OpenAI (future)
- **Monitoring**: Prometheus, Grafana (optional)
- **Storage**: S3, GCS for large-scale deployments

### Development Tools

- **Testing**: pytest framework
- **Linting**: black, isort, flake8
- **Type Checking**: mypy
- **Documentation**: Sphinx with ReadTheDocs
