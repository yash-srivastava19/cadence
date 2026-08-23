"""Pack a knapsack. Cadence rewrites this file; it never touches items.py."""

from items import CAPACITY, ITEMS


def pack(items, capacity):
    return []


chosen = pack(ITEMS, CAPACITY)
weight = sum(ITEMS[i][0] for i in chosen)
value = sum(ITEMS[i][1] for i in chosen) if weight <= CAPACITY else 0
print(f"value: {value}")
