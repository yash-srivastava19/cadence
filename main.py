"""
Main execution script for Cadence evolution experiments.

This script orchestrates the evolutionary process with comprehensive
type safety and Pydantic model validation.
"""

import logging
import json
import hydra
from omegaconf import DictConfig
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime
from src.database import sample, add, get_best_program
from src.evaluator import execute
from src.evolve import apply_diff
from src.prompt_sampler import build, update_instruction, INSTRUCTION_TEMPLATE
from src.prompt_sampler import extract_code_blocks
from src.llm import generate, mutate_instruction
from src.tasks.tsp_task import TSPTask
from src.meta_prompting import get_lesson_from_history
from src.models import ProgramCode

# Initialize task
task = TSPTask()

# Configure logging
logger = logging.getLogger(__name__)

# # Global state with proper typing
EXPERIMENT_LOG: List[Dict[str, Any]] = []
LESSON_HISTORY: List[str] = []

# # File paths
LOG_PATH: Path = Path("experiment_log.json")
LESSON_LOG_PATH: Path = Path("lesson_history.json")


def initialize_experiment() -> None:
    """Initialize experiment with baseline program if needed."""
    # global EXPERIMENT_LOG

    existing_parent, _ = sample(generation_number=0)
    if not existing_parent:
        logger.info("No program found in generation 0. Adding task baseline.")
        metric = execute(task.baseline_program, task)["cost"]
        add(program_code=task.baseline_program, metric=metric)
        logger.info(f"Baseline added with cost: {metric}")


def load_experiment_log() -> Set[int]:
    """
    Load experiment log from disk.

    Returns:
        Set of completed generation numbers
    """
    # global EXPERIMENT_LOG

    if LOG_PATH.exists():
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                EXPERIMENT_LOG = json.load(f)
            completed_generations = {entry["generation"] for entry in EXPERIMENT_LOG}
            logger.info(f"Loaded {len(EXPERIMENT_LOG)} entries from experiment log")
            return completed_generations
        except json.JSONDecodeError:
            logger.warning("Experiment log file is corrupted. Starting fresh.")
            EXPERIMENT_LOG = []
            return set()
        except Exception as e:
            logger.error(f"Failed to load experiment log: {e}")
            EXPERIMENT_LOG = []
            return set()
    else:
        EXPERIMENT_LOG = []
        return set()


def load_lesson_history() -> None:
    """Load lesson history from disk."""
    # global LESSON_HISTORY

    if LESSON_LOG_PATH.exists():
        try:
            with open(LESSON_LOG_PATH, "r", encoding="utf-8") as f:
                LESSON_HISTORY = json.load(f)
            logger.info(f"Loaded {len(LESSON_HISTORY)} lessons from history")
        except json.JSONDecodeError:
            logger.warning("Lesson history file is corrupted. Starting fresh.")
            LESSON_HISTORY = []
        except Exception as e:
            logger.error(f"Failed to load lesson history: {e}")
            LESSON_HISTORY = []
    else:
        LESSON_HISTORY = []


def save_experiment_log() -> None:
    """Save experiment log to disk."""
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(EXPERIMENT_LOG, f, indent=2, ensure_ascii=False)
        logger.debug("Experiment log saved")
    except Exception as e:
        logger.error(f"Failed to save experiment log: {e}")


def save_lesson_history() -> None:
    """Save lesson history to disk."""
    try:
        with open(LESSON_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(LESSON_HISTORY, f, indent=2, ensure_ascii=False)
        logger.debug("Lesson history saved")
    except Exception as e:
        logger.error(f"Failed to save lesson history: {e}")


def run_generation(
    generation: int,
    parent_program: ProgramCode,
    inspirations: List[str],
    LESSON_INTERVAL: int = 2,
) -> Optional[Dict[str, Any]]:
    """
    Run a single generation of evolution.

    Args:
        generation: Generation number
        parent_program: Parent program code
        inspirations: List of inspiration programs

    Returns:
        Generation result dictionary or None if failed
    """
    try:
        # Get lesson if available
        lesson = None
        if generation % LESSON_INTERVAL == 0 and LESSON_HISTORY:
            lesson = LESSON_HISTORY[-1]  # Most recent lesson

        # Build prompt
        prompt = build(parent_program, inspirations, lesson)

        # Generate child program
        child_program_blocks = generate(prompt)

        if not child_program_blocks:
            logger.warning(
                f"Generation {generation}: No code blocks generated, falling back to parent code blocks"
            )
            # Fallback: extract blocks from parent program
            parent_code = parent_program[3] if parent_program else task.baseline_program
            child_program_blocks = extract_code_blocks(parent_code)
            if not child_program_blocks:
                logger.error(
                    f"Generation {generation}: Fallback extraction yielded no blocks, aborting generation"
                )
                return None

        # Apply diff to create child program
        child_program_code = apply_diff(parent_program[3], child_program_blocks)

        # Evaluate child program
        child_result = execute(child_program_code, task)

        # Store in database
        add(
            program_code=child_program_code,
            metric=child_result["cost"],
            parent_id=parent_program[0] if parent_program else None,
        )

        # Create experiment log entry
        log_entry = {
            "generation": generation,
            "program_code": child_program_code,
            "cost": child_result["cost"],
            "feasibility": child_result["feasibility"],
            "parent_id": parent_program[0] if parent_program else None,
            "timestamp": datetime.now().isoformat(),
        }

        EXPERIMENT_LOG.append(log_entry)

        logger.info(
            f"Generation {generation}: Cost = {child_result['cost']:.2f}, "
            f"Feasibility = {child_result['feasibility']:.2f}"
        )

        return log_entry

    except Exception as e:
        logger.error(f"Generation {generation} failed: {e}")
        return None


@hydra.main(version_base=None, config_path="conf", config_name="main_config")
def main(cfg: DictConfig) -> None:
    """Main execution function."""
    # Initialize experiment
    initialize_experiment()

    # Load existing data
    completed_generations = load_experiment_log()
    load_lesson_history()

    logger.info("Starting Cadence evolution experiment")
    if cfg.FORCE_RERUN:
        logger.info("Force rerun enabled. Resetting logs.")
        completed_generations = set()
        if LOG_PATH.exists():
            LOG_PATH.unlink()
        if LESSON_LOG_PATH.exists():
            LESSON_LOG_PATH.unlink()

    # Main evolution loop
    for generation in range(
        cfg.START_GENERATION, cfg.NUM_GENERATIONS + cfg.START_GENERATION
    ):
        # Skip completed generations
        if generation in completed_generations:
            logger.info(f"Skipping generation {generation} - already completed.")
            continue

        logger.info(f"=== Generation {generation} ===")

        # Evolve meta prompt periodically
        if generation > 0 and generation % cfg.META_PROMPT_EDIT_INTERVAL == 0:
            logger.info("Evolving meta prompt...")
            try:
                new_instruction = mutate_instruction(INSTRUCTION_TEMPLATE)
                update_instruction(new_instruction)
                logger.info(f"Updated instruction: {new_instruction}")
            except Exception as e:
                logger.error(f"Failed to update instruction: {e}")

        # Select parent program (with elitism)
        parent_program = None
        inspirations: List[str] = []

        try:
            if generation > 0 and generation % cfg.ELITISM_INTERVAL == 0:
                parent_program = get_best_program()
                if parent_program:
                    logger.info(
                        f"Elitism: Using best program ID {parent_program[0]} (Cost: {parent_program[4]:.4f})"
                    )
                else:
                    logger.warning("No best program found for elitism")
                    continue
            else:
                parent_program, inspirations = sample(generation_number=generation - 1)
                if parent_program:
                    logger.info(f"Sampled parent program ID: {parent_program[0]}")
                else:
                    logger.warning("No parent program found")
                    continue
        except Exception as e:
            logger.error(f"Failed to select parent: {e}")
            continue

        # Run generation
        result = run_generation(
            generation,
            parent_program,
            inspirations,
            LESSON_INTERVAL=cfg.LESSON_INTERVAL,
        )
        if result:
            # Extract lessons periodically
            if generation % cfg.LESSON_INTERVAL == 0:
                logger.info("Extracting lesson from history...")
                try:
                    previous_lesson = LESSON_HISTORY[-1] if LESSON_HISTORY else None
                    lesson = get_lesson_from_history(
                        EXPERIMENT_LOG, previous_lesson=previous_lesson
                    )
                    if lesson:
                        LESSON_HISTORY.append(lesson)
                        logger.info(f"New lesson extracted: {lesson}")
                        save_lesson_history()
                except Exception as e:
                    logger.error(f"Failed to extract lesson: {e}")

            # Save experiment log
            save_experiment_log()
        else:
            logger.warning(f"Generation {generation} failed")

    logger.info("Experiment complete!")


if __name__ == "__main__":
    main()
