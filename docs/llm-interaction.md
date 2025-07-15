# LLM Interaction

This section describes how Cadence integrates with large language models (LLMs) to generate code mutations for optimization tasks.

## Overview

- How prompts are constructed with `src.prompt_sampler.build()`.
- Supported LLM backends and configuration.

## Usage

Example:

```python
from src.tasks.tsp_task import TSPTask
from src.prompt_sampler import build
from src.llm import generate

task = TSPTask(n_cities=10)
cities = task.generate_inputs(seed=0)
prompt = build(task, cities)
mutations = generate(prompt)
```

## Configuration

Specify API keys and model settings via environment variables (e.g., `GENAI_API_KEY`).
