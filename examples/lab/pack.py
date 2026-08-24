"""Pack a knapsack. Cadence only rewrites what lies between the markers."""

from items import CAPACITY, ITEMS

# CADENCE:BEGIN


def pack(items, capacity):
    return []


# CADENCE:END

chosen = pack(ITEMS, CAPACITY)
weight = sum(ITEMS[i][0] for i in chosen)
value = sum(ITEMS[i][1] for i in chosen) if weight <= CAPACITY else 0
print(f"value: {value}")
