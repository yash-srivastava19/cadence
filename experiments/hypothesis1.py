from src.tasks.tsp_task import generate_test_instance, compute_total_distance
from src.tasks.tsp_reference import nearest_neighbor, reversed_tour

N_SEEDS = 20
results = []

for seed in range(N_SEEDS):
    cities = generate_test_instance(seed=seed)
    nn_tour = nearest_neighbor(cities)
    rev_tour = reversed_tour(cities)

    results.append(
        {
            "seed": seed,
            "nn_cost": compute_total_distance(nn_tour, cities),
            "rev_cost": compute_total_distance(rev_tour, cities),
        }
    )

print("== Baseline Performance ==")
for r in results:
    print(
        f"Seed {r['seed']}: NN cost = {r['nn_cost']:.2f} | Reversed = {r['rev_cost']:.2f}"
    )

nn_avg = sum(r["nn_cost"] for r in results) / N_SEEDS
rev_avg = sum(r["rev_cost"] for r in results) / N_SEEDS

print(f"\nAvg NN: {nn_avg:.2f}")
print(f"Avg Reversed: {rev_avg:.2f}")
