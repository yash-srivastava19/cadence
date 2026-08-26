from collections.abc import Mapping, Sequence
from statistics import fmean

from cadence.interfaces import Metrics
from cadence.reading import MetricNotReported, read
from cadence.execution.sandboxes.subprocess import Execution, Job, Sandbox
from cadence.verdict import Failed, Outcome, Scored, Verdict, fingerprint

__all__ = ["TrialRunner"]


class TrialRunner:
    def __init__(
        self,
        program: str,
        command: Sequence[str],
        metrics: Mapping[str, str],
        sandbox: Sandbox,
        seeds: Sequence[int],
        workspace: str | None = None,
        seconds: float = 10.0,
        memory_mb: int = 256,
    ) -> None:
        if not seeds:
            raise ValueError("a trial needs at least one seed")
        if not metrics:
            raise ValueError("a trial needs at least one metric to read")
        self.program = program
        self.command = tuple(command)
        self.metrics = dict(metrics)
        self.sandbox = sandbox
        self.workspace = workspace
        self.seeds = tuple(seeds)
        self.seconds = seconds
        self.memory_mb = memory_mb

    def try_(self, code: str) -> Verdict:
        readings: list[Metrics] = []
        for seed in self.seeds:
            verdict = self._one(code, seed)
            if isinstance(verdict, Failed):
                return verdict
            readings.append(verdict.metrics)
        return Scored(fingerprint=fingerprint(code), metrics=_mean(readings))

    def _one(self, code: str, seed: int) -> Verdict:
        execution = self.sandbox.run(
            Job(
                code=code,
                program=self.program,
                command=self.command,
                workspace=self.workspace,
                seed=seed,
                seconds=self.seconds,
                memory_mb=self.memory_mb,
            )
        )
        failure = _failure(fingerprint(code), execution)
        if failure is not None:
            return failure
        try:
            return Scored(
                fingerprint=fingerprint(code),
                metrics=read(execution.stdout, self.metrics),
            )
        except MetricNotReported as error:
            return Failed(
                fingerprint=fingerprint(code),
                outcome=Outcome.INVALID,
                reason=str(error),
            )


def _failure(fingerprint: str, execution: Execution) -> Failed | None:
    if execution.ok:
        return None
    if execution.timed_out:
        outcome, reason = Outcome.TIMED_OUT, "the program ran past its deadline"
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
