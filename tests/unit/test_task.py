"""
Tests for the task module.
"""

import pytest
from src.task import Task


class MockTask(Task):
    """Mock implementation of Task for testing."""

    @property
    def function_name(self) -> str:
        return "test_function"

    def generate_inputs(self, seed: int):
        return f"input_for_seed_{seed}"

    def evaluate(self, output, input_data) -> float:
        return len(str(output))  # Simple length-based evaluation

    @property
    def baseline_program(self) -> str:
        return """
def test_function(input_data):
    ### START_BLOCK
    return str(input_data)
    ### END_BLOCK
"""

    def is_feasible(self, output, *args) -> bool:
        return isinstance(output, str)


class TestTask:
    """Test Task abstract base class."""

    def test_task_is_abstract(self):
        """Test that Task cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Task()

    def test_mock_task_implementation(self):
        """Test that MockTask implements all required methods."""
        task = MockTask()

        # Test function_name property
        assert task.function_name == "test_function"

        # Test generate_inputs method
        input_data = task.generate_inputs(42)
        assert input_data == "input_for_seed_42"

        # Test evaluate method
        score = task.evaluate("test_output", "test_input")
        assert score == len("test_output")

        # Test baseline_program property
        baseline = task.baseline_program
        assert "def test_function(input_data):" in baseline
        assert "### START_BLOCK" in baseline
        assert "### END_BLOCK" in baseline

        # Test is_feasible method
        assert task.is_feasible("string_output") is True
        assert task.is_feasible(123) is False

    def test_task_subclass_must_implement_abstract_methods(self):
        """Test that Task subclasses must implement abstract methods."""

        class IncompleteTask(Task):
            pass

        with pytest.raises(TypeError):
            IncompleteTask()

    def test_task_subclass_partial_implementation(self):
        """Test Task subclass with partial implementation."""

        class PartialTask(Task):
            @property
            def function_name(self) -> str:
                return "partial_function"

            def generate_inputs(self, seed: int):
                return seed

            # Missing evaluate and baseline_program

        with pytest.raises(TypeError):
            PartialTask()

    def test_task_concrete_implementation(self):
        """Test a concrete Task implementation."""

        class ConcreteTask(Task):
            @property
            def function_name(self) -> str:
                return "concrete_function"

            def generate_inputs(self, seed: int):
                return [seed, seed * 2]

            def evaluate(self, output, input_data) -> float:
                return abs(output - sum(input_data))

            @property
            def baseline_program(self) -> str:
                return """
def concrete_function(data):
    ### START_BLOCK
    return sum(data)
    ### END_BLOCK
"""

            def is_feasible(self, output, *args) -> bool:
                return isinstance(output, (int, float))

        task = ConcreteTask()

        # Test all methods work
        assert task.function_name == "concrete_function"

        inputs = task.generate_inputs(5)
        assert inputs == [5, 10]

        score = task.evaluate(20, inputs)
        assert score == 5.0  # abs(20 - 15)

        assert task.is_feasible(10) is True
        assert task.is_feasible("not_a_number") is False

        baseline = task.baseline_program
        assert "def concrete_function(data):" in baseline

    def test_task_default_is_feasible(self):
        """Test that default is_feasible returns True."""

        class MinimalTask(Task):
            @property
            def function_name(self) -> str:
                return "minimal"

            def generate_inputs(self, seed: int):
                return seed

            def evaluate(self, output, input_data) -> float:
                return 0.0

            @property
            def baseline_program(self) -> str:
                return "def minimal(): pass"

        task = MinimalTask()

        # Default is_feasible should return True
        assert task.is_feasible("anything") is True
        assert task.is_feasible(123) is True
        assert task.is_feasible(None) is True

    def test_task_generate_inputs_deterministic(self):
        """Test that generate_inputs produces deterministic outputs."""
        task = MockTask()

        # Same seed should produce same output
        input1 = task.generate_inputs(42)
        input2 = task.generate_inputs(42)
        assert input1 == input2

        # Different seeds should produce different outputs
        input3 = task.generate_inputs(43)
        assert input1 != input3

    def test_task_evaluate_numeric_output(self):
        """Test that evaluate returns numeric output."""
        task = MockTask()

        score = task.evaluate("test", "input")
        assert isinstance(score, (int, float))
        assert score >= 0  # Length should be non-negative

    def test_task_baseline_program_format(self):
        """Test that baseline_program has correct format."""
        task = MockTask()

        baseline = task.baseline_program

        # Should be a string
        assert isinstance(baseline, str)

        # Should contain function definition
        assert f"def {task.function_name}" in baseline

        # Should contain start/end markers
        assert "### START_BLOCK" in baseline
        assert "### END_BLOCK" in baseline

        # Should be valid Python (basic syntax check)
        try:
            compile(baseline, "<string>", "exec")
        except SyntaxError:
            pytest.fail("Baseline program should be valid Python")

    def test_task_method_signatures(self):
        """Test that Task methods have correct signatures."""
        task = MockTask()

        # Test function_name is a property
        assert hasattr(MockTask, "function_name")
        assert isinstance(getattr(MockTask, "function_name"), property)

        # Test baseline_program is a property
        assert hasattr(MockTask, "baseline_program")
        assert isinstance(getattr(MockTask, "baseline_program"), property)

        # Test methods are callable
        assert callable(task.generate_inputs)
        assert callable(task.evaluate)
        assert callable(task.is_feasible)
