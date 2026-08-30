"""A fixed-size cache, scored on how often it already had what was asked for.

Only the marked region is yours to change. Everything outside it -- the
workload, the capacity, how the score is computed -- stays put, or two runs
would not be comparable.
"""

from workload import requests

CAPACITY = 50


# CADENCE:BEGIN
class Cache:
    """Least recently used.

    Keeps whatever was touched most recently and evicts the rest. Simple,
    and it is what most caches start as.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.order: list[int] = []
        self.held: set[int] = set()

    def get(self, key: int) -> bool:
        """True if the key was already cached. Either way it is cached after."""
        if key in self.held:
            self.order.remove(key)
            self.order.append(key)
            return True
        if len(self.order) >= self.capacity:
            self.held.remove(self.order.pop(0))
        self.order.append(key)
        self.held.add(key)
        return False


# CADENCE:END


def main() -> None:
    cache = Cache(CAPACITY)
    trace = requests()
    hits = sum(cache.get(key) for key in trace)
    print(f"hit_rate: {hits / len(trace):.4f}")


if __name__ == "__main__":
    main()
