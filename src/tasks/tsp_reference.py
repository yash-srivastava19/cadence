import math


def distance(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def nearest_neighbor(cities):
    n = len(cities)
    unvisited = set(range(1, n))
    tour = [0]
    while unvisited:
        last = tour[-1]
        next_city = min(unvisited, key=lambda x: distance(cities[last], cities[x]))
        tour.append(next_city)
        unvisited.remove(next_city)
    return tour


def reversed_tour(cities):
    return list(reversed(range(len(cities))))
