# Getting Started

This guide will help you set up and run Cadence for the first time.

## Prerequisites

- Python 3.11 or higher
- Git
- Access to Google Gemini API (for LLM calls)

## Installation

### Method 1: Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/cadence
cd cadence

# Install dependencies using uv
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Method 2: Using pip

```bash
# Clone the repository
git clone https://github.com/your-org/cadence
cd cadence

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Configuration

### API Keys

Cadence requires access to a Large Language Model. Currently, Google Gemini is supported:

1. Obtain a Google Gemini API key from [Google AI Studio](https://makersuite.google.com/)
2. Set the environment variable:

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or create a `.env` file in the project root:

```bash
echo "GOOGLE_API_KEY=your-api-key-here" > .env
```

### Database Setup

Cadence uses SQLite for data storage. The database is automatically created on first run:

```bash
# The database will be created at: cadence_db.sqlite
# No manual setup required
```

## Basic Usage

### Running Evolution

Start the evolution process with default settings:

```bash
python main.py
```

This will:
- Initialize the TSP task with 10 cities
- Create an initial population
- Run 50 generations of evolution
- Save results to the database

### Customizing Parameters

```bash
# Run with custom parameters
python main.py --generations 100 --population-size 20 --cities 15
```

### Launching the Web Interface

Monitor evolution progress in real-time:

```bash
python ui/launch_ui.py
```

Then open http://localhost:5000 in your browser.

### Using Hydra Configuration

Cadence leverages Hydra for flexible, YAML-driven settings. All experiment scripts accept `--config-name` and override parameters at the CLI.

```bash
# List available config options
python run_h1_experiment.py --help

# Override parameters without editing YAML
python run_h1_experiment.py SEEDS=5 GENERATIONS=50 LESSON_INTERVAL=4

# Point to alternate config directory
python run_h1_experiment.py --config-path ./conf --config-name custom_h1
```

Hydra creates an `outputs/` folder by default; to write to project root, set in your YAML:
```yaml
hydra:
  run:
    dir: .
  output:
    subdir: null
```

## Verification

### Test Installation

```bash
# Run the test suite
pytest

# Run with coverage
pytest --cov=src
```

### Quick Validation

```bash
# Test LLM connection
python -c "from src.llm import LLM; llm = LLM(); print(llm.generate('Hello'))"

# Test database connection
python -c "from src.database import Database; db = Database(); print('Database OK')"
```

## First Run Example

Here's what happens during your first evolution run:

```bash
$ python main.py

Initializing Cadence Evolution System
=====================================
Task: TSP with 10 cities
Population size: 10
Generations: 50
LLM: Google Gemini

Generation 1/50
- Created 10 initial programs
- Best cost: 245.67
- Average cost: 892.34

Generation 2/50
- Evolved 10 programs
- Best cost: 198.23 (improved!)
- Average cost: 456.78

...

Evolution completed!
Final best cost: 89.45
Results saved to cadence_db.sqlite
Launch UI with: python ui/launch_ui.py
```

## Common Issues

### API Key Issues

```bash
# Error: No API key found
export GOOGLE_API_KEY="your-key"

# Error: Invalid API key
# Check your key at https://makersuite.google.com/
```

### Import Errors

```bash
# Error: Module not found
pip install -e .

# Or ensure you're in the right directory
cd cadence
python main.py
```

### Database Permissions

```bash
# Error: Permission denied on database
chmod 664 cadence_db.sqlite

# Or remove and recreate
rm cadence_db.sqlite
python main.py
```

## Next Steps

- Read the [Architecture](architecture.md) guide to understand system components
- Explore [Tasks](tasks.md) to create custom optimization problems
- Check out [Examples](examples.md) for more usage patterns
- Review [Configuration](configuration.md) for advanced settings
