# Configuration

This document describes how to configure Cadence for different use cases and environments.

## Configuration Hierarchy

Cadence uses a layered configuration approach:

1. **Default Values**: Built-in defaults in source code
2. **Configuration Files**: JSON/YAML files for structured settings
3. **Environment Variables**: Runtime configuration and secrets
4. **Command Line Arguments**: Override specific parameters

## Configuration Files

### Basic Configuration

Create `config.json` in the project root:

```json
{
  "evolution": {
    "population_size": 20,
    "generations": 100,
    "elite_size": 2,
    "tournament_size": 3,
    "mutation_rate": 0.8,
    "stagnation_threshold": 10
  },
  "llm": {
    "provider": "google",
    "model": "gemini-pro",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 30
  },
  "evaluation": {
    "num_seeds": 10,
    "timeout": 30,
    "parallel": true,
    "max_workers": 4
  },
  "database": {
    "path": "cadence_db.sqlite",
    "backup_interval": 100
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "cadence.log"
  }
}
```

### Task-Specific Configuration

```json
{
  "tasks": {
    "tsp": {
      "n_cities": 20,
      "distance_metric": "euclidean",
      "constraint_type": "standard"
    },
    "knapsack": {
      "n_items": 50,
      "capacity": 100,
      "item_generation": "uniform"
    }
  }
}
```

### Experiment Configuration

```json
{
  "experiment": {
    "name": "tsp_comparison_study",
    "description": "Compare different prompt strategies",
    "runs": 10,
    "save_intermediate": true,
    "metrics": ["cost", "diversity", "convergence_time"],
    "conditions": [
      {
        "name": "baseline",
        "instructions": "Improve the TSP solution",
        "temperature": 0.7
      },
      {
        "name": "detailed",
        "instructions": "Focus on algorithmic improvements and edge cases",
        "temperature": 0.5
      }
    ]
  }
}
```

## Environment Variables

### Required Variables

```bash
# LLM API credentials
export GOOGLE_API_KEY="your-gemini-api-key"

# Optional: Alternative providers
export OPENAI_API_KEY="your-openai-api-key"
```

### Optional Variables

```bash
# Database configuration
export CADENCE_DB_PATH="/path/to/database.sqlite"
export CADENCE_DB_BACKUP=true

# Logging configuration
export CADENCE_LOG_LEVEL="DEBUG"
export CADENCE_LOG_FILE="/path/to/cadence.log"

# Performance tuning
export CADENCE_TIMEOUT=60
export CADENCE_MAX_WORKERS=8
export CADENCE_MEMORY_LIMIT="4GB"

# Development settings
export CADENCE_DEBUG=true
export CADENCE_PROFILE=true
```

### Using .env Files

Create `.env` in project root:

```bash
# .env
GOOGLE_API_KEY=your-api-key-here
CADENCE_LOG_LEVEL=DEBUG
CADENCE_DB_PATH=./data/cadence.sqlite
CADENCE_MAX_WORKERS=4
```

Load automatically:

```python
from dotenv import load_dotenv
load_dotenv()
```

## Command Line Configuration

### Basic Usage

```bash
# Override specific parameters
python main.py --generations 200 --population-size 30

# Use custom config file
python main.py --config experiments/config.json

# Set logging level
python main.py --log-level DEBUG

# Specify output directory
python main.py --output-dir ./results/experiment_1
```

### Available Arguments

```bash
python main.py --help

Options:
  --config PATH              Configuration file path
  --generations INTEGER      Number of generations to run
  --population-size INTEGER  Population size
  --task TEXT               Task type (tsp, knapsack)
  --cities INTEGER          Number of cities for TSP
  --output-dir PATH         Output directory for results
  --log-level TEXT          Logging level (DEBUG, INFO, WARN, ERROR)
  --parallel / --no-parallel Enable/disable parallel evaluation
  --save-intermediate       Save intermediate results
  --resume PATH             Resume from checkpoint
```

## Configuration Loading

### Programmatic Configuration

```python
from src.config import Config

# Load from file
config = Config.from_file("config.json")

# Load from environment
config = Config.from_env()

# Combine sources
config = Config()
config.load_file("config.json")
config.load_env()
config.update_from_args(args)

# Access configuration
print(config.evolution.population_size)
print(config.llm.temperature)
```

### Dynamic Configuration

```python
# Update during runtime
config.evolution.population_size = 50
config.llm.temperature = 0.5

# Conditional configuration
if config.debug:
    config.logging.level = "DEBUG"
    config.evaluation.parallel = False
```

## Advanced Configuration

### Profile-Based Configuration

Create different profiles for different environments:

```json
{
  "profiles": {
    "development": {
      "evolution": {"generations": 10, "population_size": 5},
      "logging": {"level": "DEBUG"},
      "evaluation": {"parallel": false}
    },
    "production": {
      "evolution": {"generations": 200, "population_size": 50},
      "logging": {"level": "INFO"},
      "evaluation": {"parallel": true, "max_workers": 16}
    },
    "research": {
      "evolution": {"generations": 1000, "population_size": 100},
      "logging": {"level": "INFO"},
      "evaluation": {"num_seeds": 50}
    }
  }
}
```

Usage:

```bash
python main.py --profile production
```

### Conditional Configuration

```json
{
  "evolution": {
    "population_size": "${CADENCE_POPULATION_SIZE:20}",
    "generations": "${CADENCE_GENERATIONS:100}"
  },
  "database": {
    "path": "${CADENCE_DB_PATH:./cadence_db.sqlite}"
  }
}
```

### Configuration Validation

```python
from src.config import ConfigValidator

validator = ConfigValidator()

# Validate configuration
errors = validator.validate(config)
if errors:
    for error in errors:
        print(f"Configuration error: {error}")
    exit(1)

# Validate specific sections
validator.validate_evolution_config(config.evolution)
validator.validate_llm_config(config.llm)
```

## Performance Tuning

### CPU-Intensive Tasks

```json
{
  "evaluation": {
    "parallel": true,
    "max_workers": null,  // Use all available cores
    "chunk_size": 10,
    "timeout": 60
  }
}
```

### Memory-Constrained Environments

```json
{
  "evolution": {
    "population_size": 10,  // Smaller population
    "batch_size": 5        // Process in batches
  },
  "database": {
    "lazy_loading": true,   // Load data on demand
    "compression": true     // Compress stored data
  }
}
```

### High-Throughput Settings

```json
{
  "llm": {
    "batch_requests": true,
    "request_pooling": 10,
    "cache_responses": true
  },
  "evaluation": {
    "parallel": true,
    "max_workers": 20,
    "async_evaluation": true
  }
}
```

## Deployment Configuration

### Docker Configuration

```dockerfile
# Environment variables in Dockerfile
ENV GOOGLE_API_KEY=""
ENV CADENCE_LOG_LEVEL="INFO"
ENV CADENCE_DB_PATH="/data/cadence.sqlite"
ENV CADENCE_MAX_WORKERS="4"

# Copy configuration
COPY config/production.json /app/config.json
```

### Kubernetes Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cadence-config
data:
  config.json: |
    {
      "evolution": {
        "population_size": 20,
        "generations": 100
      },
      "database": {
        "path": "/data/cadence.sqlite"
      }
    }
---
apiVersion: v1
kind: Secret
metadata:
  name: cadence-secrets
type: Opaque
stringData:
  google-api-key: "your-api-key-here"
```

### Cloud Configuration

```json
{
  "cloud": {
    "provider": "aws",
    "storage": {
      "bucket": "cadence-results",
      "region": "us-west-2"
    },
    "compute": {
      "instance_type": "c5.2xlarge",
      "auto_scaling": true
    }
  },
  "monitoring": {
    "cloudwatch": true,
    "metrics_interval": 60
  }
}
```

## Configuration Best Practices

### Security

```bash
# Never commit API keys
echo "*.env" >> .gitignore
echo "config/secrets.json" >> .gitignore

# Use environment variables for secrets
export GOOGLE_API_KEY=$(cat /path/to/secure/api-key)

# Rotate keys regularly
export GOOGLE_API_KEY_BACKUP="old-key-for-transition"
```

### Organization

```
config/
├── base.json           # Common settings
├── development.json    # Dev overrides
├── production.json     # Prod settings
├── testing.json        # Test configuration
└── experiments/
    ├── tsp_study.json
    └── algorithm_comparison.json
```

### Documentation

```json
{
  "_comments": {
    "population_size": "Number of programs in each generation",
    "generations": "Total generations to run",
    "temperature": "LLM creativity parameter (0.0-1.0)"
  },
  "evolution": {
    "population_size": 20,
    "generations": 100
  }
}
```

### Validation

```python
# config_schema.json
{
  "type": "object",
  "properties": {
    "evolution": {
      "type": "object",
      "properties": {
        "population_size": {"type": "integer", "minimum": 1},
        "generations": {"type": "integer", "minimum": 1}
      },
      "required": ["population_size", "generations"]
    }
  },
  "required": ["evolution"]
}
```

## Troubleshooting

### Common Issues

**Configuration not loading:**
```bash
# Check file path
ls -la config.json

# Validate JSON syntax
python -m json.tool config.json
```

**Environment variables not found:**
```bash
# Check variables are set
env | grep CADENCE

# Load from .env file
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GOOGLE_API_KEY'))"
```

**Permission errors:**
```bash
# Check file permissions
ls -la cadence_db.sqlite

# Fix permissions
chmod 664 cadence_db.sqlite
```

### Debug Configuration

```python
# Print effective configuration
from src.config import Config
config = Config.load()
print(config.to_dict())

# Trace configuration sources
print(config.get_source("evolution.population_size"))
# Output: "environment variable CADENCE_POPULATION_SIZE"
```
