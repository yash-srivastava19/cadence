#!/usr/bin/env python3
"""
Test runner script for Cadence test suite.

This script provides convenient commands for running different types of tests
with appropriate configurations and reporting.
"""

import argparse
import subprocess
import sys


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 60}")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
    else:
        print(f"❌ {description} - FAILED")

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run Cadence tests")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "integration", "performance", "coverage", "quick"],
        help="Type of tests to run",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--parallel", "-p", action="store_true", help="Run tests in parallel"
    )
    parser.add_argument(
        "--bail", "-x", action="store_true", help="Stop on first failure"
    )

    args = parser.parse_args()

    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]

    if args.verbose:
        base_cmd.append("-v")

    if args.parallel:
        base_cmd.extend(["-n", "auto"])

    if args.bail:
        base_cmd.append("-x")

    # Test paths
    unit_path = "tests/unit/"
    integration_path = "tests/integration/"
    performance_path = "tests/performance/"

    success = True

    if args.test_type == "unit":
        cmd = [*base_cmd, unit_path]
        success = run_command(cmd, "Unit Tests")

    elif args.test_type == "integration":
        cmd = [*base_cmd, integration_path]
        success = run_command(cmd, "Integration Tests")

    elif args.test_type == "performance":
        cmd = [*base_cmd, performance_path, "--durations=10"]
        success = run_command(cmd, "Performance Tests")

    elif args.test_type == "coverage":
        cmd = [
            *base_cmd,
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80",
            unit_path,
            integration_path,
        ]
        success = run_command(cmd, "Coverage Tests")

    elif args.test_type == "quick":
        # Run only fast unit tests
        cmd = [*base_cmd, unit_path, "-m", "not slow"]
        success = run_command(cmd, "Quick Tests")

    elif args.test_type == "all":
        # Run all test categories in sequence
        test_suites = [
            ([*base_cmd, unit_path], "Unit Tests"),
            ([*base_cmd, integration_path], "Integration Tests"),
            ([*base_cmd, performance_path], "Performance Tests"),
        ]

        for cmd, description in test_suites:
            if not run_command(cmd, description):
                success = False
                if args.bail:
                    break

    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
