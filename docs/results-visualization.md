# Results Visualization

This section explains how to visualize evolution results using plots.

## Evolution Progress Plot

- Use `matplotlib` or `plotly` to plot cost metrics over generations.
- Example:

```python
import matplotlib.pyplot as plt
from src.database import Database, DatabaseConfig

# Load data
 db = Database(DatabaseConfig(database_path='evolution.db'))
 entries = db.get_all_programs()
 gens = [e.generation_number for e in entries]
 costs = [e.metric for e in entries]

# Plot progress
 plt.figure(figsize=(8, 4))
 plt.plot(gens, costs, marker='o')
 plt.title('Evolution Progress')
 plt.xlabel('Generation')
 plt.ylabel('Tour Cost')
 plt.grid(True)
 plt.show()
```

## Histograms and Distributions

- Plot histograms of metrics to observe distribution of solutions.

```python
import seaborn as sns
sns.histplot(costs, bins=10)
sns.despine()
```
