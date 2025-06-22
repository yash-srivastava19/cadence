import logging
import json
from ..src.tasks.tsp_task import TSPTask
from ..src.evaluator import execute
from ..src.prompt_sampler import build
from ..src.rl.agent import RLAgent


# Setup
logging.basicConfig(level=logging.INFO)
NUM_GENERATIONS = 20
SEEDS = [1, 2, 3, 4, 5]
EXPERIMENT_LOG = []

# Initialize task and agent
task = TSPTask()
agent = RLAgent(task)

for generation in range(NUM_GENERATIONS):
    logging.info(f"\n=== RL Generation {generation} ===")

    # Step 1: Create synthetic parent (no inspiration history in RL for now)
    parent_program = None
    inspirations = []

    # Step 2: Build prompt
    prompt = build(parent_program, inspirations)

    # Step 3: Generate code using LLM (agent action)
    try:
        child_program_code = agent.sample_action(prompt)
    except Exception as e:
        logging.error(f"LLM generation failed: {e}")
        continue

    # Step 4: Evaluate
    result = execute(child_program_code, task, seeds=SEEDS)

    if "error" in result and result["error"]:
        logging.warning(f"Evaluation error: {result['error']}")
        reward = -1e6  # harsh penalty
    else:
        reward = -result["cost"]
        logging.info(f"Avg Cost: {result['cost']:.4f}, Reward: {reward:.4f}")

    # Step 5: Record (state, action, reward)
    agent.observe(prompt, child_program_code, reward)

    # Step 6: Log for visualization
    EXPERIMENT_LOG.append({
        "generation": generation,
        "prompt": prompt,
        "code": child_program_code,
        "cost": result.get("cost", float("inf")),
        "reward": reward,
    })

# Save logs
with open("rl_experiment_log.json", "w") as f:
    json.dump(EXPERIMENT_LOG, f, indent=2)

logging.info("RL training complete. Log saved to rl_experiment_log.json")
