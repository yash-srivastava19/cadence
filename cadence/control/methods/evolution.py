import random
from hashlib import sha256

from cadence.control.entities import Candidate
from cadence.exceptions import NoCandidates
from cadence.interfaces import Attempt, Directive, History, Ledger, Objective
from cadence.verdict import Verdict

__all__ = ["HINTS", "Evolution", "Member", "rng_for"]

HINTS = (
    "make it faster without changing what it returns",
    "handle the case the current code ignores",
    "replace the inner loop with something cheaper",
    "try a different strategy entirely",
)


def rng_for(run_id: str, index: int) -> random.Random:
    digest = sha256(f"{run_id}/{index}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


class Member:
    def __init__(self, candidate: Candidate, verdict: Verdict | None = None) -> None:
        self.candidate = candidate
        self.verdict = verdict

    @property
    def measured(self) -> bool:
        return self.verdict is not None

    @property
    def attempt(self) -> Attempt:
        return Attempt(code=self.candidate.code, verdict=self.verdict)


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

    def better(self, one: Member, two: Member) -> bool:
        if not one.measured:
            return False
        if not two.measured:
            return True
        return self.objective.dominates(one.verdict.metrics, two.verdict.metrics)

    def population(self, history: History) -> list[Member]:
        living = [Member(Candidate(code=code)) for code in history.seeds]
        for attempt in history.attempts:
            if not attempt.verdict.is_scored:
                continue
            living.append(Member(Candidate(code=attempt.code), attempt.verdict))
            while len(living) > self.size:
                living.remove(self.weakest(living))
        return living

    def best(self, history: History) -> Attempt | None:
        winner = None
        for member in self.population(history):
            if winner is None or self.better(member, winner):
                winner = member
        return winner.attempt if winner is not None and winner.measured else None

    def pick(self, living: list[Member], rng: random.Random) -> Member:
        entrants = [rng.choice(living) for _ in range(self.tournament)]
        winner = entrants[0]
        for entrant in entrants[1:]:
            if self.better(entrant, winner):
                winner = entrant
        return winner

    def weakest(self, living: list[Member]) -> Member:
        loser = living[0]
        for member in living[1:]:
            if self.better(loser, member):
                loser = member
        return loser

    def next_directive(self, history: History, ledger: Ledger) -> Directive | None:
        if ledger.exhausted:
            return None
        living = self.population(history)
        if not living:
            raise NoCandidates("every candidate has been retired")
        parent = self.pick(living, rng_for(history.run_id, history.index))
        return Directive(
            parent=parent.candidate.fingerprint,
            code=parent.candidate.code,
            hint=HINTS[history.index % len(HINTS)],
        )
