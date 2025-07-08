# Cadence Test Suite

This directory contains a comprehensive test suite for the Cadence evolution system, organized into specialized categories for different testing needs.

## Test Structure

```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for component interactions
├── performance/       # Performance and benchmarking tests
├── fixtures/          # Shared test data and utilities
├── conftest.py       # pytest configuration and fixtures
└── run_tests.py      # Test runner script
```

## Test Categories

### Unit Tests (`unit/`)
- **Purpose**: Test individual components in isolation
- **Files**:
  - `test_database.py` - Database operations and queries
  - `test_evaluator.py` - Code evaluation functionality
  - `test_evolve.py` - Evolution algorithms and strategies
  - `test_llm.py` - LLM provider interfaces
  - `test_prompt_sampler.py` - Prompt generation and sampling
  - `test_task.py` - Task definitions and management
- **Coverage**: Focuses on individual methods, edge cases, and error handling

### Integration Tests (`integration/`)
- **Purpose**: Test component interactions and end-to-end workflows
- **Files**:
  - `test_integration.py` - Basic component integration
  - `test_end_to_end.py` - Complete evolution workflows
- **Coverage**: Multi-component scenarios, data flow, system behavior

### Performance Tests (`performance/`)
- **Purpose**: Benchmark performance and scalability
- **Files**:
  - `test_benchmarks.py` - Performance and scalability tests
- **Coverage**: Speed, memory usage, concurrent access, large datasets

### Fixtures (`fixtures/`)
- **Purpose**: Shared test data and mock objects
- **Files**:
  - `sample_code.py` - Example code snippets
  - `mock_responses.py` - Mock LLM responses
  - `test_configs.json` - Test configurations
- **Usage**: Reusable test data across multiple test files

## Running Tests

### All Tests
```bash
# Run complete test suite
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run with detailed output
pytest -v
```

### Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Performance tests only
pytest tests/performance/

# Specific test file
pytest tests/unit/test_database.py

# Specific test function
pytest tests/unit/test_database.py::TestDatabase::test_create_connection
```

### Performance Testing
```bash
# Run performance tests with timing
pytest tests/performance/ -v --durations=10

# Run memory profiling tests
pytest tests/performance/ -m memory_profile

# Skip slow performance tests
pytest -m "not slow"
```

## Test Configuration

### pytest Markers
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.memory_profile` - Memory usage tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.unit` - Unit tests

### Environment Variables
- `CADENCE_TEST_DB` - Custom test database path
- `CADENCE_TEST_TIMEOUT` - Test timeout duration
- `CADENCE_MOCK_LLM` - Use mock LLM for testing

## Test Data Management

### Database Tests
- Use temporary databases created per test
- Automatic cleanup after test completion
- Isolated test data to prevent interference

### Mock Objects
- Mock LLM providers for deterministic testing
- Sample code repositories for evaluation tests
- Configurable test scenarios

### Fixtures
- Shared fixtures in `conftest.py`
- Category-specific fixtures in test files
- Parameterized tests for multiple scenarios

## Writing New Tests

### Unit Test Guidelines
```python
class TestComponentName:
    """Test suite for ComponentName."""

    def test_specific_functionality(self, fixture_name):
        """Test specific functionality with clear description."""
        # Arrange
        component = ComponentName()

        # Act
        result = component.method_under_test()

        # Assert
        assert result == expected_value
```

### Integration Test Guidelines
```python
def test_component_integration(self, system_fixtures):
    """Test integration between multiple components."""
    # Set up system
    system = create_test_system()

    # Execute workflow
    result = system.execute_workflow()

    # Verify end-to-end behavior
    assert_workflow_completed_successfully(result)
```

### Performance Test Guidelines
```python
def test_performance_requirement(self, large_dataset):
    """Test that operation meets performance requirements."""
    start_time = time.time()

    # Execute operation
    component.process_large_dataset(large_dataset)

    end_time = time.time()

    # Assert performance requirement
    assert (end_time - start_time) < MAX_ACCEPTABLE_TIME
```

## Continuous Integration

The test suite is designed to run in CI environments with:
- Automatic test discovery
- Parallel test execution where safe
- Coverage reporting
- Performance regression detection
- Dependency isolation

## Test Maintenance

### Regular Tasks
- Update mock data when APIs change
- Add tests for new features
- Remove tests for deprecated functionality
- Monitor test performance and optimize slow tests

### Quality Standards
- Minimum 80% code coverage
- All tests must be deterministic
- Performance tests should have clear baselines
- Integration tests should be isolated and repeatable
python -m tests.run_tests
```

## Test Categories

### Unit Tests
- `test_database.py`: Tests database operations in isolation
- `test_evaluator.py`: Tests code evaluation and execution
- `test_evolve.py`: Tests diff application and program modification
- `test_llm.py`: Tests LLM interactions (mocked)
- `test_prompt_sampler.py`: Tests prompt building logic
- `test_task.py`: Tests task interface compliance

### Integration Tests
- `test_integration.py`: Tests complete evolution workflows
- Tests interaction between multiple components
- Tests realistic scenarios

## Test Markers

Tests are marked with the following categories:
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow-running tests
- `@pytest.mark.llm`: Tests requiring LLM API access

## Fixtures

Common test fixtures are provided in `conftest.py`:
- `temp_database`: Temporary SQLite database for testing
- `mock_llm_client`: Mocked LLM client for testing
- `sample_tsp_program`: Sample TSP implementation
- `sample_cities`: Sample city coordinates

## Coverage Targets

Aim for:
- **90%+ line coverage** overall
- **95%+ coverage** for core modules (database, evaluator, evolve)
- **100% coverage** for critical paths and error handling

## Running with PyRight

Type checking is configured for the test suite:
```bash
pyright tests/
```

## Test Data

Tests use:
- Temporary databases (automatically cleaned up)
- Deterministic random seeds for reproducibility
- Mocked external API calls
- Sample programs and data fixtures

## Adding New Tests

When adding new functionality:
1. Add unit tests for the individual components
2. Add integration tests for component interactions
3. Update fixtures if needed
4. Add appropriate markers
5. Ensure good test coverage

## Continuous Integration

These tests are designed to run in CI environments:
- No external dependencies required (APIs are mocked)
- Deterministic behavior
- Fast execution (slow tests can be excluded)
- Clear error messages and reporting
