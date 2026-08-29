from collections.abc import Mapping, Sequence
from importlib.metadata import version
from statistics import fmean

from cadence.core.identity import fingerprint, hash_of
from cadence.core.types import Metrics
from cadence.core.verdict import Failed, Failure, Outcome, Scored, Verdict
from cadence.errors import MetricNotReported
from cadence.execution.sandboxes.subprocess import (
    Execution,
    Job,
    Sandbox,
    workspace_digest,
)
from cadence.parsing.metrics import read, verifier_broke

__all__ = ["MEASUREMENT_EPOCH", "TrialRunner"]

#: Bumped by hand whenever cadence changes what a score means -- how a metric
#: is read, how a failure is classified, what the sandbox does. The package
#: version cannot do this job on its own: it stays 0.1.0 across every commit
#: that would change a result.
MEASUREMENT_EPOCH = 1


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

    @property
    def task_hash(self) -> str:
        """The identity of the measurement, candidate and seeds aside.

        Everything that decides what running a candidate does: where it is
        written, what is run, which numbers are read, the limits it is run
        under, and every other file that lands beside it. Not the model, the
        budget or the search method -- those choose what to measure, never
        what the measurement is.
        """
        return hash_of(
            {
                "epoch": MEASUREMENT_EPOCH,
                "cadence": version("cadence"),
                "program": self.program,
                "command": list(self.command),
                "metrics": sorted(self.metrics),
                "seconds": self.seconds,
                "memory_mb": self.memory_mb,
                "workspace": workspace_digest(self.workspace, self.program),
            }
        )

    @property
    def seeds_hash(self) -> str:
        """Which seeds a score was averaged over. Two of three is a different
        measurement, not a partial one."""
        return hash_of({"seeds": list(self.seeds)})

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
        broke = verifier_broke(execution.stdout)
        if broke is not None:
            # Not the candidate's fault, so not a score. Escalating stops the
            # run: an expired key in a verifier would otherwise score every
            # candidate at the floor and report success.
            return Failed(
                fingerprint=fingerprint(code),
                outcome=Outcome.VERIFIER_ERROR,
                reason=f"the scoring command reported a fault of its own: {broke}",
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
    outcome: Failure
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
