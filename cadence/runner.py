import json
from collections.abc import Sequence
from statistics import fmean

from cadence.entities import Candidate
from cadence.interfaces import Metrics, Task
from cadence.sandbox import UNSERIALIZABLE, Execution, Job, Sandbox
from cadence.verdict import Failed, Outcome, Scored, Verdict

__all__ = ["TrialRunner"]

DEFAULT_SEEDS = (0, 1, 2)


class TrialRunner:
    def __init__(
        self,
        task: Task,
        sandbox: Sandbox,
        seeds: Sequence[int] = DEFAULT_SEEDS,
        seconds: float = 10.0,
        memory_mb: int = 256,
    ) -> None:
        if not seeds:
            raise ValueError("a trial needs at least one seed")
        self.task = task
        self.sandbox = sandbox
        self.seeds = tuple(seeds)
        self.seconds = seconds
        self.memory_mb = memory_mb

    def try_(self, candidate: Candidate) -> Verdict:
        readings: list[Metrics] = []
        for seed in self.seeds:
            verdict = self._one(candidate, seed)
            if isinstance(verdict, Failed):
                return verdict
            readings.append(verdict.metrics)
        return Scored(fingerprint=candidate.fingerprint, metrics=_mean(readings))

    def _one(self, candidate: Candidate, seed: int) -> Verdict:
        inputs = self.task.inputs(seed)
        execution = self.sandbox.run(
            Job(
                code=candidate.code,
                entry_point=self.task.entry_point,
                seed=seed,
                seconds=self.seconds,
                memory_mb=self.memory_mb,
            ),
            inputs=json.dumps([inputs]),
        )
        failure = _failure(candidate.fingerprint, execution)
        if failure is not None:
            return failure
        try:
            output = json.loads(execution.stdout)
        except json.JSONDecodeError:
            return Failed(
                fingerprint=candidate.fingerprint,
                outcome=Outcome.INVALID,
                reason="the program did not return something serializable",
            )
        return self._score(candidate, output, inputs)

    def _score(self, candidate: Candidate, output, inputs) -> Verdict:
        try:
            metrics = self.task.score(output, inputs)
        except Exception as error:
            return Failed(
                fingerprint=candidate.fingerprint,
                outcome=Outcome.VERIFIER_ERROR,
                reason=f"{type(error).__name__}: {error}",
            )
        if not metrics:
            return Failed(
                fingerprint=candidate.fingerprint,
                outcome=Outcome.VERIFIER_ERROR,
                reason="the task scored nothing",
            )
        return Scored(fingerprint=candidate.fingerprint, metrics=metrics)


def _failure(fingerprint: str, execution: Execution) -> Failed | None:
    if execution.ok:
        return None
    if execution.timed_out:
        outcome, reason = Outcome.TIMED_OUT, "the program ran past its deadline"
    elif execution.exit_status == UNSERIALIZABLE:
        outcome, reason = Outcome.INVALID, _tail(execution.stderr)
    elif execution.out_of_memory:
        outcome, reason = Outcome.OUT_OF_MEMORY, "the program ran out of memory"
    else:
        outcome, reason = Outcome.CRASHED, _tail(execution.stderr)
    return Failed(fingerprint=fingerprint, outcome=outcome, reason=reason)


def _tail(stderr: str, lines: int = 3) -> str:
    kept = [line for line in stderr.strip().splitlines() if line.strip()]
    return "\n".join(kept[-lines:]) or "the program failed without saying why"


def _mean(readings: Sequence[Metrics]) -> Metrics:
    return {name: fmean(r[name] for r in readings) for name in readings[0]}
