import random
from math import sqrt
from src.task import Task

class TSPTask(Task):
    def __init__(self, n_cities=10):
        self.n_cities = n_cities

    @property
    def function_name(self):
        return "tsp"

    def generate_inputs(self, seed: int):
        random.seed(seed)
        return [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(self.n_cities)]

    def evaluate(self, output, cities) -> float:
        if not isinstance(output, list) or sorted(output) != list(range(len(cities))):
            return float("inf")

        def dist(i, j):
            x1, y1 = cities[i]
            x2, y2 = cities[j]
            return sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

        total = 0
        for i in range(len(output)):
            total += dist(output[i], output[(i + 1) % len(output)])
        return total

    @property
    def baseline_program(self) -> str:
        return """### START_BLOCK
    def tsp(cities):
        return list(range(len(cities)))
    ### END_BLOCK"""
