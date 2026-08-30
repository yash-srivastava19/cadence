"""The access pattern the cache is scored against.

Two things happen in it, and they pull in opposite directions:

- a small hot set, requested over and over. Keeping these is the whole job.
- periodic sequential scans over a large cold range. Each scan touches every
  key exactly once and never comes back.

That combination is the classic reason plain LRU disappoints in production:
a scan is the most-recently-used thing in the cache, so LRU evicts the hot
set to make room for keys nobody will ask for again.

Fixed seed, so two runs of the same policy score the same. Nothing here is
inside the region the model may edit.
"""

import random

HOT = 40
COLD_START = 1_000
SCAN = 300
ROUNDS = 60
REQUESTS_PER_ROUND = 200


def requests() -> list[int]:
    rng = random.Random(20260830)
    trace: list[int] = []
    for round_ in range(ROUNDS):
        for _ in range(REQUESTS_PER_ROUND):
            # 85% of traffic is the hot set, which is what a cache is for.
            if rng.random() < 0.85:
                trace.append(rng.randrange(HOT))
            else:
                trace.append(rng.randrange(HOT, HOT + 200))
        # Every fourth round, something walks a big cold range once.
        if round_ % 4 == 3:
            base = COLD_START + rng.randrange(50) * SCAN
            trace.extend(range(base, base + SCAN))
    return trace
