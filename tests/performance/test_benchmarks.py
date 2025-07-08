"""Performance and benchmarking tests for Cadence components."""

import pytest
import time
import memory_profiler
import concurrent.futures

from src.database import Database
from src.evaluator import Evaluator
from src.evolve import Evolver


class TestDatabasePerformance:
    """Performance tests for database operations."""

    @pytest.fixture
    def large_dataset(self):
        """Generate a large dataset for performance testing."""
        return [
            {
                "code": f"def solution_{i}(x): return x * {i}",
                "fitness": i * 0.01,
                "metrics": {"time": i * 0.1, "memory": i * 1000},
            }
            for i in range(1000)
        ]

    def test_bulk_insert_performance(self, temp_database, large_dataset):
        """Test performance of bulk database insertions."""
        db = Database(temp_database)

        start_time = time.time()
        run_id = db.create_run("performance_test", "bulk_insert")

        # Insert in batches
        batch_size = 100
        for i in range(0, len(large_dataset), batch_size):
            batch = large_dataset[i : i + batch_size]
            db.store_generation(run_id, i // batch_size, batch)

        end_time = time.time()
        insertion_time = end_time - start_time

        # Should be able to insert 1000 records in reasonable time
        assert insertion_time < 10.0  # 10 seconds max

        # Verify all data was inserted
        run_summary = db.get_run_summary(run_id)
        assert run_summary["generation_count"] == 10  # 1000/100 batches

    def test_query_performance(self, temp_database, large_dataset):
        """Test performance of database queries."""
        db = Database(temp_database)
        run_id = db.create_run("query_performance_test", "query_test")

        # Insert test data
        for i, data in enumerate(large_dataset[:100]):  # Smaller dataset for setup
            db.store_generation(run_id, i, [data])

        # Test query performance
        start_time = time.time()
        for _ in range(100):  # 100 queries
            generations = db.get_generations(run_id)
            max(gen["fitness"] for gen in generations)
        end_time = time.time()

        query_time = end_time - start_time
        assert query_time < 5.0  # Should complete 100 queries in under 5 seconds

    def test_concurrent_access(self, temp_database):
        """Test database performance under concurrent access."""
        db = Database(temp_database)

        def worker_task(worker_id):
            """Task for concurrent workers."""
            run_id = db.create_run(f"concurrent_test_{worker_id}", "concurrent")

            for i in range(10):
                result = {
                    "code": f"def worker_{worker_id}_gen_{i}(): pass",
                    "fitness": worker_id * 0.1 + i * 0.01,
                }
                db.store_generation(run_id, i, [result])

            return worker_id

        # Run concurrent workers
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_task, i) for i in range(5)]
            results = [future.result() for future in futures]
        end_time = time.time()

        # All workers should complete successfully
        assert len(results) == 5
        assert sorted(results) == [0, 1, 2, 3, 4]

        # Should complete in reasonable time
        total_time = end_time - start_time
        assert total_time < 15.0


class TestEvaluatorPerformance:
    """Performance tests for code evaluation."""

    def test_evaluation_speed(self, sample_task):
        """Test speed of code evaluation."""
        evaluator = Evaluator()

        test_codes = [f"def solution_{i}(x): return x * {i}" for i in range(50)]

        start_time = time.time()
        results = []
        for code in test_codes:
            result = evaluator.evaluate_code(code, sample_task)
            results.append(result)
        end_time = time.time()

        evaluation_time = end_time - start_time
        avg_time_per_eval = evaluation_time / len(test_codes)

        # Should evaluate quickly
        assert avg_time_per_eval < 0.1  # 100ms per evaluation max
        assert all(r is not None for r in results)

    @pytest.mark.skipif(
        not hasattr(memory_profiler, "profile"), reason="memory_profiler not available"
    )
    def test_memory_usage(self, sample_task):
        """Test memory usage during evaluation."""
        evaluator = Evaluator()

        # Test with increasingly complex code
        complex_code = """
def solution(x):
    # Create some memory usage
    data = list(range(1000))
    result = sum(i * i for i in data)
    return result % len(x) if x else 0
"""

        # Monitor memory during evaluation
        import psutil

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        for _ in range(10):
            evaluator.evaluate_code(complex_code, sample_task)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory usage shouldn't grow excessively
        assert memory_increase < 50 * 1024 * 1024  # 50MB max increase


class TestEvolverPerformance:
    """Performance tests for code evolution."""

    def test_evolution_speed(self, mock_llm_provider, sample_task):
        """Test speed of code evolution."""
        evolver = Evolver(mock_llm_provider)

        initial_codes = [f"def solution_{i}(x): return x + {i}" for i in range(10)]

        start_time = time.time()
        evolved_codes = []

        for i, code in enumerate(initial_codes):
            result = {"fitness": i * 0.1, "code": code}
            evolved = evolver.evolve_code(code, result, sample_task, generation=1)
            evolved_codes.append(evolved)

        end_time = time.time()
        evolution_time = end_time - start_time
        avg_time_per_evolution = evolution_time / len(initial_codes)

        # Evolution should be reasonably fast
        assert avg_time_per_evolution < 2.0  # 2 seconds per evolution max
        assert all(len(code) > 0 for code in evolved_codes)

    def test_batch_evolution_performance(self, mock_llm_provider, sample_task):
        """Test performance of batch evolution operations."""
        evolver = Evolver(mock_llm_provider)

        # Create a population
        population = [
            {"code": f"def solution_{i}(x): return x * {i}", "fitness": i * 0.1}
            for i in range(20)
        ]

        start_time = time.time()

        # Evolve entire population
        evolved_population = []
        for individual in population:
            evolved_code = evolver.evolve_code(
                individual["code"], individual, sample_task, generation=1
            )
            evolved_population.append(evolved_code)

        end_time = time.time()

        batch_time = end_time - start_time
        assert batch_time < 30.0  # 30 seconds for 20 individuals
        assert len(evolved_population) == len(population)


class TestSystemScalability:
    """Test system scalability and resource limits."""

    def test_large_code_handling(self, sample_task):
        """Test handling of large code snippets."""
        evaluator = Evaluator()

        # Generate large code snippet
        large_code = (
            """
def solution(x):
    # Large function with many operations
"""
            + "\n".join([f"    result_{i} = sum(range({i}))" for i in range(100)])
            + """
    return sum(["""
            + ", ".join([f"result_{i}" for i in range(100)])
            + """])
"""
        )

        start_time = time.time()
        result = evaluator.evaluate_code(large_code, sample_task)
        end_time = time.time()

        # Should handle large code without excessive delay
        evaluation_time = end_time - start_time
        assert evaluation_time < 5.0
        assert result is not None

    def test_long_running_experiment(
        self, temp_database, mock_llm_provider, sample_task
    ):
        """Test system behavior during long-running experiments."""
        db = Database(temp_database)
        evaluator = Evaluator()
        evolver = Evolver(mock_llm_provider)

        run_id = db.create_run("long_running_test", "scalability")
        code = "def solution(x): return sum(x) if x else 0"

        # Simulate long experiment
        start_time = time.time()
        for generation in range(50):  # 50 generations
            result = evaluator.evaluate_code(code, sample_task)
            db.store_generation(run_id, generation, [result])

            if generation < 49:
                code = evolver.evolve_code(code, result, sample_task, generation + 1)

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in reasonable time
        assert total_time < 120.0  # 2 minutes max

        # Verify data integrity
        run_summary = db.get_run_summary(run_id)
        assert run_summary["generation_count"] == 50
