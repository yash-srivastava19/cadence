# Contributing

We welcome contributions to Cadence! This document outlines how to contribute effectively to the project.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- uv (recommended) or pip

### Setting Up Development Environment

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/cadence.git
   cd cadence
   ```

2. **Create Development Environment**
   ```bash
   # Using uv (recommended)
   uv sync --dev

   # Or using pip
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

4. **Verify Setup**
   ```bash
   # Run tests
   pytest

   # Run linting
   black --check src/
   isort --check-only src/
   flake8 src/

   # Type checking
   mypy src/
   ```

## Development Workflow

### Branching Strategy

We use Git Flow with the following branch types:

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Critical production fixes

### Making Changes

1. **Create Feature Branch**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Develop and Test**
   ```bash
   # Make your changes

   # Run tests frequently
   pytest tests/unit/

   # Check code quality
   black src/
   isort src/
   flake8 src/
   mypy src/
   ```

3. **Commit Changes**
   ```bash
   # Stage changes
   git add .

   # Commit with descriptive message
   git commit -m "feat: add multi-objective optimization support"
   ```

4. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(llm): add OpenAI provider support
fix(database): resolve connection timeout issue
docs: update API documentation
test(evolve): add unit tests for apply_diff function
```

## Code Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

```python
# Line length: 88 characters (Black default)
# Use double quotes for strings
# Import ordering: standard library, third-party, local

# Example function
def evolve_program(
    parent_code: str,
    llm: LLM,
    instructions: str,
    temperature: float = 0.7
) -> str:
    """Evolve a program using LLM mutations.

    Args:
        parent_code: Source code to evolve
        llm: Language model interface
        instructions: Evolution instructions
        temperature: LLM creativity parameter

    Returns:
        Evolved program code

    Raises:
        LLMError: If LLM call fails
        ValueError: If parent_code is invalid
    """
    if not parent_code.strip():
        raise ValueError("Parent code cannot be empty")

    try:
        response = llm.generate(
            prompt=f"{instructions}\n\nCode:\n{parent_code}",
            temperature=temperature
        )
        return parse_response(response)
    except Exception as e:
        raise LLMError(f"Evolution failed: {e}") from e
```

### Type Hints

Use type hints for all public APIs:

```python
from typing import Dict, List, Optional, Union, Any
from pathlib import Path

def analyze_results(
    results: List[Dict[str, Any]],
    output_path: Optional[Path] = None
) -> Dict[str, Union[float, int, str]]:
    """Analyze experiment results."""
    pass
```

### Documentation

**Docstring Format:**
```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """Brief description of the function.

    Longer description if needed. Explain the purpose, behavior,
    and any important details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ExceptionType: When this exception is raised

    Example:
        >>> result = function_name("value1", 42)
        >>> print(result)
        expected_output
    """
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/              # Unit tests
│   ├── test_task.py
│   ├── test_evolve.py
│   └── test_llm.py
├── integration/       # Integration tests
│   ├── test_evaluator.py
│   └── test_database_integration.py
├── performance/       # Performance tests
│   └── test_benchmarks.py
├── fixtures/          # Test data
│   ├── sample_code.py
│   └── mock_responses.py
└── conftest.py        # Shared fixtures
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from unittest.mock import Mock, patch
from src.evolve import apply_diff

class TestApplyDiff:
    """Test the apply_diff function."""

    def test_single_block_replacement(self):
        """Test replacing a single marked block."""
        parent_code = """
def example():
    ### START_BLOCK
    return "old"
    ### END_BLOCK
"""
        diffs = ["return \"new\""]

        result = apply_diff(parent_code, diffs)

        assert "return \"new\"" in result
        assert "return \"old\"" not in result
        assert "def example():" in result

    def test_multiple_blocks(self):
        """Test replacing multiple marked blocks."""
        parent_code = """
def example():
    ### START_BLOCK
    x = 1
    ### END_BLOCK

    ### START_BLOCK
    y = 2
    ### END_BLOCK
    return x + y
"""
        diffs = ["x = 10", "y = 20"]

        result = apply_diff(parent_code, diffs)

        assert "x = 10" in result
        assert "y = 20" in result
        assert "return x + y" in result

    def test_no_blocks_unchanged(self):
        """Test that code without blocks remains unchanged."""
        code = "def example():\n    return 42"
        diffs = ["x = 1"]

        result = apply_diff(code, diffs)

        assert result == code

    @pytest.mark.parametrize("diffs", [[], None])
    def test_empty_diffs(self, diffs):
        """Test handling of empty diff lists."""
        code = "def example():\n    ### START_BLOCK\n    pass\n    ### END_BLOCK"

        result = apply_diff(code, diffs or [])

        assert result == code
```

**Integration Test Example:**
```python
import pytest

from src.evaluator import execute
from src.tasks.tsp_task import TSPTask


class TestEvaluation:
    @pytest.fixture
    def task(self):
        return TSPTask(n_cities=8)

    def test_baseline_is_feasible(self, task):
        result = execute(task.baseline_program, task)
        assert result["feasibility"] == 1.0
        assert result["cost"] < 1e8

    def test_broken_program_is_infeasible(self, task):
        broken = "### START_BLOCK\ndef tsp(cities):\n    return [0, 0, 0]\n### END_BLOCK"
        assert execute(broken, task)["cost"] == 1e8
```

There is no `MockLLM` and no `EvolutionSystem`. Tests that need a model
should mock `src.llm.generate` with `pytest-mock`, which is already a
dependency:

```python
def test_generation_uses_the_prompt(mocker):
    fake = mocker.patch("src.llm.generate", return_value=["def tsp(c): return []"])
    ...
    assert fake.called
```


### Test Configuration

```python
# conftest.py
import pytest
import tempfile
import os
from unittest.mock import Mock

@pytest.fixture
def temp_database():
    """Provide temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def mock_llm():
    """Provide mock LLM for testing."""
    llm = Mock()
    llm.generate.return_value = "return list(range(len(cities)))"
    return llm

@pytest.fixture
def sample_tsp_task():
    """Provide sample TSP task for testing."""
    from src.tasks.tsp_task import TSPTask
    return TSPTask(n_cities=5)
```

## Pull Request Process

### Before Submitting

1. **Ensure Tests Pass**
   ```bash
   pytest tests/ -v
   ```

2. **Check Code Quality**
   ```bash
   black --check src/ tests/
   isort --check-only src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

3. **Update Documentation**
   - Add docstrings for new functions
   - Update API documentation if needed
   - Add examples for new features

4. **Write Tests**
   - Unit tests for new functions
   - Integration tests for new features
   - Update existing tests if behavior changes

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] No new warnings introduced
```

### Review Process

1. **Automated Checks**
   - CI/CD pipeline runs tests
   - Code quality checks
   - Documentation builds

2. **Code Review**
   - At least one maintainer approval required
   - Address all review comments
   - Ensure backward compatibility

3. **Merge**
   - Squash and merge for features
   - Merge commit for releases

## Architecture Guidelines

### Adding New Tasks

1. **Inherit from Task Base Class**
   ```python
   from src.task import Task

   class NewTask(Task):
       def __init__(self, param1: Type1, param2: Type2):
           self.param1 = param1
           self.param2 = param2
   ```

2. **Implement Required Methods**
   - `function_name`: Return function name to extract
   - `generate_inputs`: Create deterministic test inputs
   - `evaluate`: Assess solution quality
   - `baseline_program`: Provide working template

3. **Add Tests**
   ```python
   # tests/tasks/test_new_task.py
   class TestNewTask:
       def test_input_generation(self):
           # Test deterministic input creation

       def test_evaluation(self):
           # Test solution evaluation

       def test_baseline_program(self):
           # Test that baseline program works
   ```

4. **Document the Task**
   - Add to `docs/tasks.md`
   - Include usage examples
   - Document parameters and behavior

### Adding New LLM Providers

1. **Implement LLM Interface**
   ```python
   from src.llm import LLMProvider

   class NewProviderLLM(BaseLLM):
       def __init__(self, api_key: str, model: str):
           self.api_key = api_key
           self.model = model

       def generate(self, prompt: str, **kwargs) -> str:
           # Implement API call
           pass
   ```

2. **Add Configuration Support**
   ```python
   # In src/llm.py
   def create_llm(provider: str, **kwargs) -> BaseLLM:
       if provider == "new_provider":
           return NewProviderLLM(**kwargs)
       # ... existing providers
   ```

3. **Add Tests and Documentation**

### Database Schema Changes

1. **Create Migration Script**
   ```python
   # migrations/001_add_new_table.py
   def upgrade(connection):
       connection.execute("""
           CREATE TABLE new_table (
               id INTEGER PRIMARY KEY,
               data TEXT NOT NULL
           )
       """)

   def downgrade(connection):
       connection.execute("DROP TABLE new_table")
   ```

2. **Update Database Class**
   ```python
   def add_new_data(self, data: str) -> int:
       """Add new data to database."""
       cursor = self.connection.cursor()
       cursor.execute(
           "INSERT INTO new_table (data) VALUES (?)",
           (data,)
       )
       return cursor.lastrowid
   ```

## Release Process

### Version Management

We use [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes

### Release Steps

1. **Update Version Numbers**
   ```python
   # pyproject.toml
   version = "1.2.0"
   ```

2. **Update Changelog**
   ```markdown
   ## [1.2.0] - 2025-07-08

   ### Added
   - Multi-objective optimization support
   - OpenAI provider integration

   ### Fixed
   - Database connection timeout issues

   ### Changed
   - Improved LLM prompt formatting
   ```

3. **Create Release**
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```

4. **Publish to PyPI**
   ```bash
   uv build
   uv publish
   ```

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **GitHub Discussions**: Ask questions or discuss ideas
- **Discord**: Real-time chat with maintainers (link in README)
- **Email**: Direct contact for sensitive issues

## Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- Annual contributor highlights

Thank you for contributing to Cadence!
