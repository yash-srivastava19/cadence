"""
Pydantic models for Cadence data structures.

This module defines typed data models using Pydantic for validation
and serialization of common data structures throughout the system.
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum


class TaskType(str, Enum):
    """Supported task types."""

    TSP = "tsp"
    KNAPSACK = "knapsack"
    CUSTOM = "custom"


class ExperimentStatus(str, Enum):
    """Experiment execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationResult(BaseModel):
    """Result of code evaluation."""

    model_config = ConfigDict(frozen=True)

    cost: float = Field(..., description="Evaluation cost (lower is better)")
    feasible: bool = Field(..., description="Whether solution is feasible")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")
    execution_time: Optional[float] = Field(
        None, description="Execution time in seconds"
    )
    memory_usage: Optional[int] = Field(None, description="Memory usage in bytes")

    @validator("cost")
    def validate_cost(cls, v: float) -> float:
        """Ensure cost is non-negative."""
        if v < 0:
            raise ValueError("Cost must be non-negative")
        return v


class ProgramEntry(BaseModel):
    """Database entry for a program."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Unique program ID")
    generation: int = Field(..., ge=0, description="Generation number")
    parent_id: Optional[int] = Field(None, description="Parent program ID")
    code: str = Field(..., min_length=1, description="Program source code")
    metric: float = Field(..., description="Program performance metric")
    instance_id: Optional[int] = Field(None, description="Test instance ID")
    diff: Optional[str] = Field(None, description="Diff from parent")
    prompt: Optional[str] = Field(None, description="Generation prompt")
    timestamp: Optional[str] = Field(None, description="Creation timestamp")


class GenerationSummary(BaseModel):
    """Summary of a generation."""

    model_config = ConfigDict(frozen=True)

    generation: int = Field(..., ge=0)
    program_count: int = Field(..., ge=0)
    best_cost: float = Field(...)
    average_cost: float = Field(...)
    worst_cost: float = Field(...)
    feasible_count: int = Field(..., ge=0)

    @validator("feasible_count")
    def validate_feasible_count(cls, v: int, values: Dict[str, Any]) -> int:
        """Ensure feasible_count <= program_count."""
        if "program_count" in values and v > values["program_count"]:
            raise ValueError("Feasible count cannot exceed program count")
        return v


class ExperimentConfig(BaseModel):
    """Configuration for evolution experiments."""

    model_config = ConfigDict(frozen=True)

    task_type: TaskType = Field(..., description="Type of optimization task")
    num_generations: int = Field(50, ge=1, description="Number of generations to run")
    population_size: int = Field(10, ge=1, description="Population size per generation")
    elitism_interval: int = Field(20, ge=1, description="Interval for elitism")
    meta_prompt_interval: int = Field(10, ge=1, description="Meta-prompting interval")
    lesson_interval: int = Field(2, ge=1, description="Lesson extraction interval")

    # Task-specific parameters
    tsp_cities: Optional[int] = Field(10, ge=3, description="Number of cities for TSP")
    evaluation_seeds: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])

    # LLM parameters
    llm_model: str = Field("gemini-2.0-flash", description="LLM model name")
    # llm_temperature: float = Field(0.7, ge=0.0, le=2.0, description="LLM temperature")
    max_retries: int = Field(3, ge=0, description="Max LLM API retries")


class LLMResponse(BaseModel):
    """Response from LLM API."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    prompt_tokens: Optional[int] = Field(None, ge=0, description="Input token count")
    completion_tokens: Optional[int] = Field(
        None, ge=0, description="Output token count"
    )
    finish_reason: Optional[str] = Field(None, description="Completion finish reason")


class CodeBlock(BaseModel):
    """Extracted code block."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(..., min_length=1, description="Code content")
    start_line: Optional[int] = Field(None, ge=1, description="Start line number")
    end_line: Optional[int] = Field(None, ge=1, description="End line number")
    language: Optional[str] = Field("python", description="Programming language")

    @validator("end_line")
    def validate_end_line(
        cls, v: Optional[int], values: Dict[str, Any]
    ) -> Optional[int]:
        """Ensure end_line >= start_line."""
        if (
            v is not None
            and "start_line" in values
            and values["start_line"] is not None
        ):
            if v < values["start_line"]:
                raise ValueError("End line must be >= start line")
        return v


class TaskInstance(BaseModel):
    """Test instance for optimization tasks."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Instance ID")
    seed: int = Field(..., description="Random seed")
    task_type: TaskType = Field(..., description="Task type")
    data: Dict[str, Any] = Field(..., description="Instance-specific data")

    # TSP-specific fields
    cities: Optional[List[Tuple[float, float]]] = Field(
        None, description="City coordinates for TSP"
    )
    optimal_cost: Optional[float] = Field(None, description="Known optimal cost")


class ExperimentRun(BaseModel):
    """Complete experiment run data."""

    id: str = Field(..., description="Unique run identifier")
    config: ExperimentConfig = Field(..., description="Experiment configuration")
    status: ExperimentStatus = Field(ExperimentStatus.PENDING, description="Run status")
    start_time: Optional[str] = Field(None, description="Start timestamp")
    end_time: Optional[str] = Field(None, description="End timestamp")
    generations: List[GenerationSummary] = Field(default_factory=list)
    best_program: Optional[ProgramEntry] = Field(None, description="Best program found")
    error_message: Optional[str] = Field(None, description="Error if run failed")

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate run duration in seconds."""
        if self.start_time and self.end_time:
            from datetime import datetime

            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            return (end - start).total_seconds()
        return None


class PromptTemplate(BaseModel):
    """Template for LLM prompts."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Template name")
    template: str = Field(..., min_length=1, description="Prompt template string")
    variables: List[str] = Field(default_factory=list, description="Template variables")
    description: Optional[str] = Field(None, description="Template description")


class LessonHistory(BaseModel):
    """Historical lessons learned from evolution."""

    lessons: List[str] = Field(default_factory=list, description="List of lessons")
    generation_created: List[int] = Field(
        default_factory=list, description="Generation when lesson was created"
    )

    def add_lesson(self, lesson: str, generation: int) -> None:
        """Add a new lesson."""
        self.lessons.append(lesson)
        self.generation_created.append(generation)

    def get_recent_lessons(self, n: int = 3) -> List[Tuple[str, int]]:
        """Get the N most recent lessons."""
        if not self.lessons:
            return []

        paired = list(zip(self.lessons, self.generation_created))
        return paired[-n:] if len(paired) >= n else paired


class DatabaseConfig(BaseModel):
    """Database configuration."""

    model_config = ConfigDict(frozen=True)

    database_path: str = Field("cadence_db.sqlite", description="Database file path")
    connection_timeout: float = Field(
        30.0, ge=0, description="Connection timeout seconds"
    )
    enable_wal_mode: bool = Field(True, description="Enable WAL mode for SQLite")
    backup_interval: Optional[int] = Field(
        None, ge=0, description="Backup interval in minutes"
    )


# Type aliases for commonly used types
CityCoordinates = Tuple[float, float]
Tour = List[int]
MetricValue = Union[int, float]
ProgramCode = str
PromptText = str
