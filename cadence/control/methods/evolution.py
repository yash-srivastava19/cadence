"""Tournament selection over a fixed-size population.

The whole search, in three sentences: keep the best few programs seen so far,
pick a parent by holding a small tournament between random members, and evict
the weakest once there are too many. Which program wins a comparison is the
Objective's business, never this file's.
"""

import random
from collections.abc import Callable, Sequence
from hashlib import sha256

from cadence.control.entities import Candidate
from cadence.core.dto import Attempt, Directive, History, Ledger
from cadence.core.ports import Objective
from cadence.core.values import Value
from cadence.core.verdict import Scored
from cadence.errors import NoCandidates

__all__ = ["Evolution", "Measured", "Unmeasured"]


class Unmeasured(Value):
    """A program in the population that has not been scored.

    The seeds start here. It can be chosen as a parent and it can be evicted;
    it can never win a comparison, because there is nothing to compare.
    """

    model_config = Value.model_config | {"arbitrary_types_allowed": True}

    candidate: Candidate


class Measured(Value):
    """A program and what it scored.

    Two classes rather than one with `verdict: Verdict | None`: the guard
    `if not member.measured` used to stand in front of every use of
    `.metrics`, and forgetting it was a runtime error the type checker could
    not warn about. Now the type says which one you are holding.
    """

    model_config = Value.model_config | {"arbitrary_types_allowed": True}

    candidate: Candidate
    verdict: Scored

    @property
    def attempt(self) -> Attempt:
        return Attempt(code=self.candidate.code, verdict=self.verdict)


Individual = Measured | Unmeasured
Better = Callable[[Individual, Individual], bool]


def _rng_for(run_id: str, index: int) -> random.Random:
    """Seeded from the run and the trial, so parent choice replays exactly.

    Not from the clock and not from a shared global: a replayed run has to
    hold the same tournaments it held the first time.
    """
    digest = sha256(f"{run_id}/{index}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _extreme(members: Sequence[Individual], better: Better) -> Individual:
    """The one nothing beats, by whichever comparison is handed in.

    best, the tournament winner and the eviction victim were three copies of
    this loop. They differ only in the comparison and in what is being
    compared.
    """
    chosen = members[0]
    for member in members[1:]:
        if better(member, chosen):
            chosen = member
    return chosen


class Evolution:
    def __init__(
        self, objective: Objective, size: int = 8, tournament: int = 3
    ) -> None:
        if tournament < 1:
            raise ValueError("a tournament needs at least one entrant")
        if size < 1:
            raise ValueError("a population needs room for at least one candidate")
        self.objective = objective
        self.size = size
        self.tournament = tournament

    def better(self, one: Individual, two: Individual) -> bool:
        if not isinstance(one, Measured):
            return False
        if not isinstance(two, Measured):
            return True
        return self.objective.dominates(one.verdict.metrics, two.verdict.metrics)

    def worse(self, one: Individual, two: Individual) -> bool:
        return self.better(two, one)

    def strongest(self, members: Sequence[Individual]) -> Individual:
        return _extreme(members, self.better)

    def weakest(self, members: Sequence[Individual]) -> Individual:
        return _extreme(members, self.worse)

    def population(self, history: History) -> list[Individual]:
        living: list[Individual] = [
            Unmeasured(candidate=Candidate(code=code)) for code in history.seeds
        ]
        for attempt in history.attempts:
            if not isinstance(attempt.verdict, Scored):
                continue
            living.append(
                Measured(
                    candidate=Candidate(code=attempt.code), verdict=attempt.verdict
                )
            )
            while len(living) > self.size:
                living.remove(self.weakest(living))
        return living

    def pick(self, living: Sequence[Individual], rng: random.Random) -> Individual:
        entrants = [rng.choice(list(living)) for _ in range(self.tournament)]
        return self.strongest(entrants)

    def best(self, history: History) -> Attempt | None:
        living = self.population(history)
        if not living:
            return None
        winner = self.strongest(living)
        return winner.attempt if isinstance(winner, Measured) else None

    def next_directive(self, history: History, ledger: Ledger) -> Directive | None:
        if ledger.exhausted:
            return None
        living = self.population(history)
        if not living:
            raise NoCandidates("every candidate has been retired")
        parent = self.pick(living, _rng_for(history.run_id, history.index))
        return Directive(
            parent=parent.candidate.fingerprint,
            code=parent.candidate.code,
            index=history.index,
        )
