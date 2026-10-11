"""The winner is chosen on seeds the search never saw.

A search keeps the best of many noisy measurements, so its best is partly
luck. This measures the method's top few again on seeds of the manifest's
choosing and ranks them on those numbers alone.
"""

from collections.abc import Sequence

from cadence.core.dto import Evidence, Picked, RunHistory, TrialResult
from cadence.core.ports import Measure, Method, Objective
from cadence.core.verdict import Failed, Scored

__all__ = ["Confirm"]


class Confirm:
    def __init__(
        self,
        method: Method,
        objective: Objective,
        seeds: Sequence[int],
        top: int = 3,
    ) -> None:
        if not seeds:
            raise ValueError("confirming needs at least one seed")
        if top < 1:
            raise ValueError("top must be at least 1")
        self.method = method
        self.objective = objective
        self.seeds = tuple(seeds)
        self.top = top

    def pick(self, history: RunHistory, measure: Measure) -> Picked | None:
        leaders = self._leaders(history)
        if not leaders:
            return None
        confirmed: list[tuple[TrialResult, Scored]] = []
        failures: list[str] = []
        for leader in leaders:
            verdict = measure(leader.code, self.seeds).verdict
            if isinstance(verdict, Failed):
                failures.append(f"{verdict.fingerprint[:12]} {verdict.outcome}")
                continue
            confirmed.append((leader, verdict))
        if not confirmed:
            # Nothing to trust on fresh seeds. The search's own best is still
            # what the run found, so it is reported, and the evidence says it
            # is unconfirmed rather than the report pretending it was.
            return Picked(
                result=leaders[0],
                evidence=Evidence(seeds=self.seeds, unconfirmed="; ".join(failures)),
            )
        winner, verdict = confirmed[0]
        for leader, candidate in confirmed[1:]:
            if self.objective.dominates(candidate.metrics, verdict.metrics):
                winner, verdict = leader, candidate
        return Picked(
            result=TrialResult(code=winner.code, verdict=verdict),
            evidence=Evidence(seeds=self.seeds, searched=winner.metrics),
        )

    def _leaders(self, history: RunHistory) -> list[TrialResult]:
        """The method's best, then its best of the rest, `top` times.

        Asked of the method rather than sorted here, so "best" keeps meaning
        whatever the method means by it, Pareto fronts included.
        """
        leaders: list[TrialResult] = []
        remaining = history.results
        while len(leaders) < self.top:
            best = self.method.best(history.model_copy(update={"results": remaining}))
            if best is None:
                break
            leaders.append(best)
            taken = best.verdict.fingerprint
            remaining = tuple(r for r in remaining if r.verdict.fingerprint != taken)
        return leaders
