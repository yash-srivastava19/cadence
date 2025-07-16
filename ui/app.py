#!/usr/bin/env python3
"""
Simple Flask UI for Cadence Experiment Visualization

This module provides a Flask web interface for visualizing
Cadence evolution experiments with comprehensive type safety.
"""

import json
import os
import sys
from typing import Dict, List, Any, Tuple
from flask import Flask, render_template, jsonify, request, Response, make_response

# Add parent directory to path to import cadence modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_all_programs

app = Flask(__name__)

# Global data storage with proper typing
experiment_data: Dict[str, Any] = {}
config_data: Dict[str, Any] = {}


def load_experiment_data(results_dir: str) -> List[Tuple[Any, ...]]:
    """
    Load experiment data from results directory.

    Args:
        results_dir: Path to the results directory

    Returns:
        List of program tuples from database
    """
    global experiment_data, config_data

    # Load config
    config_file = os.path.join(results_dir, "experiment_config.json")
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config_data = json.load(f)

    # Load results
    results_file = os.path.join(results_dir, "final_results.json")
    if os.path.exists(results_file):
        with open(results_file, "r") as f:
            experiment_data = json.load(f)

    # Load database programs
    try:
        programs = get_all_programs()
        return programs
    except Exception as e:
        print(f"Error loading database: {e}")
        return []


@app.route("/")
def index() -> str:
    """Main visualization page."""
    return render_template("index.html")


@app.route("/api/config")
def get_config() -> Response:
    """Get experiment configuration."""
    return make_response(jsonify(config_data))


def safe_metric_value(value: Any) -> float:
    """
    Convert metric value to JSON-safe format.

    Args:
        value: The metric value to convert

    Returns:
        JSON-safe float value
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        if value == float("inf") or value == float("-inf"):
            return 1000000.0 if value > 0 else -1000000.0
        if value != value:  # NaN check
            return 0.0
        return float(value)
    return 0.0


@app.route("/api/programs")
def get_programs() -> Response:
    """Get all programs from database."""
    try:
        programs = get_all_programs()
        # Convert to JSON-serializable format
        programs_json: List[Dict[str, Any]] = []
        for prog in programs:
            programs_json.append(
                {
                    "id": prog[0],
                    "generation": prog[1],
                    "parent_id": prog[2],
                    "code": prog[3],
                    "metric": safe_metric_value(prog[4]),
                    "diff": prog[5] if len(prog) > 5 else "",
                    "prompt": prog[6] if len(prog) > 6 else "",
                }
            )
        return make_response(jsonify(programs_json))
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)


@app.route("/api/program/<int:program_id>")
def get_program(program_id: int) -> Response:
    """Get specific program details."""
    try:
        programs = get_all_programs()
        for prog in programs:
            if prog[0] == program_id:
                return jsonify(
                    {
                        "id": prog[0],
                        "generation": prog[1],
                        "parent_id": prog[2],
                        "code": prog[3],
                        "metric": safe_metric_value(prog[4]),
                        "diff": prog[5] if len(prog) > 5 else "",
                        "prompt": prog[6] if len(prog) > 6 else "",
                    }
                )
        return make_response(jsonify({"error": "Program not found"}), 404)
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)


@app.route("/api/metrics")
def get_metrics() -> Response:
    """Get available metrics."""
    return make_response(jsonify(["cost", "feasibility"]))


@app.route("/api/experiment_results")
def get_experiment_results() -> Response:
    """Get experiment results."""
    return make_response(jsonify(experiment_data))


@app.route("/api/performance/<int:program_id>")
def get_performance(program_id: int) -> Response:
    """Get performance data for a specific program lineage."""
    try:
        programs = get_all_programs()

        # Find all ancestors and descendants
        lineage: List[Dict[str, Any]] = []

        def add_to_lineage(pid: int) -> None:
            for prog in programs:
                if prog[0] == pid:
                    lineage.append(
                        {
                            "id": prog[0],
                            "generation": prog[1],
                            "metric": safe_metric_value(prog[4]),
                        }
                    )
                    if prog[2]:  # has parent
                        add_to_lineage(prog[2])
                    break

        add_to_lineage(program_id)
        lineage.sort(key=lambda x: x["generation"])

        return make_response(jsonify(lineage))
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)


@app.route("/load_experiment", methods=["POST"])
def load_experiment() -> Response:
    """Load experiment from directory."""
    data = request.get_json()
    results_dir = data.get("results_dir")

    if not results_dir or not os.path.exists(results_dir):
        return jsonify({"error": "Invalid results directory"}), 400

    try:
        programs = load_experiment_data(results_dir)
        return make_response(
            jsonify({"success": True, "programs_count": len(programs)})
        )
    except Exception as e:
        return make_response(jsonify({"error": str(e)}), 500)


if __name__ == "__main__":
    # Try to load default experiment if exists
    experiments_dir = "../experiments"
    if os.path.exists(experiments_dir):
        # Find latest results directory
        result_dirs = [
            d for d in os.listdir(experiments_dir) if d.startswith("results_")
        ]
        print(result_dirs)
        if result_dirs:
            latest_dir = max(result_dirs)
            load_experiment_data(os.path.join(experiments_dir, latest_dir))
            print(f"Loaded experiment data from: {latest_dir}")

    app.run(debug=True, host="0.0.0.0", port=5000)
