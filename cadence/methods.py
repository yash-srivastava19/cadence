import random
from collections.abc import Sequence

from cadence.entities import Candidate
from cadence.exceptions import NoCandidates
from cadence.interfaces import Attempt, Directive, Metrics, Objective, Search

__all__ = ["HINTS", "Member", "Evolution"]

HINTS = (
    "make it faster without changing what it returns",
    "handle the case the current code ignores",
    "replace the inner loop with something cheaper",
    "try a different strategy entirely",
)


class Member:
    def __init__(self, candidate: Candidate, metrics: Metrics | None = None) -> None:
        self.candidate = candidate
        self.metrics = metrics

    @property
    def measured(self) -> bool:
        return self.metrics is not None


class Evolution:
    def __init__(
        self,
        objective: Objective,
        size: int = 8,
        tournament: int = 3,
        seed: int = 0,
    ) -> None:
        if tournament < 1:
            raise ValueError("a tournament needs at least one entrant")
        if size < 1:
            raise ValueError("a population needs room for at least one candidate")
        self.objective = objective
        self.size = size
        self.tournament = tournament
        self.seed = seed
        self.population: list[Member] = []

    def better(self, one: Member, two: Member) -> bool:
        if not one.measured:
            return False
        if not two.measured:
            return True
        return self.objective.dominates(one.metrics, two.metrics)

    def best(self) -> Member | None:
        winner = None
        for member in self.population:
            if winner is None or self.better(member, winner):
                winner = member
        return winner

    def pick(self, rng: random.Random) -> Member:
        entrants = [rng.choice(self.population) for _ in range(self.tournament)]
        winner = entrants[0]
        for entrant in entrants[1:]:
            if self.better(entrant, winner):
                winner = entrant
        return winner

    def admit(self, member: Member) -> None:
        self.population.append(member)
        while len(self.population) > self.size:
            self.population.remove(self.weakest())

    def weakest(self) -> Member:
        loser = self.population[0]
        for member in self.population[1:]:
            if self.better(loser, member):
                loser = member
        return loser

    def search(self, seeds: Sequence[str], budget: int) -> Search:
        self.population = [Member(Candidate(code=code)) for code in seeds]
        if not self.population:
            raise NoCandidates("a search needs at least one seed program")

        rng = random.Random(self.seed)
        for index in range(budget):
            parent = self.pick(rng)
            attempt = yield Directive(
                parent=parent.candidate.fingerprint,
                code=parent.candidate.code,
                hint=HINTS[index % len(HINTS)],
            )
            if attempt is None:
                continue
            self.record(parent, attempt)
            if not self.population:
                raise NoCandidates("every candidate has been retired")

    def record(self, parent: Member, attempt: Attempt) -> None:
        if not attempt.verdict.is_scored:
            parent.candidate.crashed()
            return
        child = Candidate(code=attempt.code, parent=parent.candidate.fingerprint)
        self.admit(Member(child, attempt.verdict.metrics))
