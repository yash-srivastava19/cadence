import logging
import json
from src.tasks.tsp_task import TSPTask
from src.evaluator import execute
from src.prompt_sampler import build
from src.rl.agent import RLAgent
from src.database import sample, add
from src.rl.reward_model import RewardModel

logging.basicConfig(level=logging.INFO)


NUM_GENERATIONS = 5
SEEDS = [1, 2, 3, 4, 5]
EXPERIMENT_LOG = []
RETRAIN_INTERVAL = 5
# Initialize task and RL agent
task = TSPTask()
agent = RLAgent(task)

reward_model = RewardModel()
agent.reward_model = reward_model

# Step 0: Ensure generation 0 has a baseline program
existing_parent, _ = sample(generation_number=0)
if not existing_parent:
    logging.info("No program found in generation 0. Adding task baseline.")
    metric = execute(task.baseline_program, task)["cost"]
    add(program_code=task.baseline_program, metric=metric)
    logging.info(f"Baseline added with cost: {metric}")

# --- Begin RL loop ---
for generation in range(NUM_GENERATIONS):
    logging.info(f"\n=== RL Generation {generation} ===")

    # Sample baseline parent to construct prompt (RL can ignore inspirations)
    parent_program, inspirations = sample(generation_number=0)
    prompt = build(parent_program, inspirations)

    if generation % RETRAIN_INTERVAL == 0 and generation > 0:
        logging.info("Retraining reward model...")
        reward_model.train(EXPERIMENT_LOG)
    # Generate code using RL agent (LLM behind the scenes)
    try:
        child_program_code = agent.sample_action(prompt)
    except Exception as e:
        logging.error(f"LLM generation failed: {e}")
        continue

    # Evaluate generated code
    result = execute(child_program_code, task, seeds=SEEDS)
    if result.get("error"):
        logging.warning(f"Evaluation error: {result['error']}")
        reward = -1e6
    else:
        reward = -result["cost"]
        logging.info(f"Avg Cost: {result['cost']:.4f}, Reward: {reward:.4f}")

    # Learn from feedback
    agent.observe(prompt, child_program_code, reward)

    # Log for analysis
    EXPERIMENT_LOG.append(
        {
            "generation": generation,
            "prompt": prompt,
            "code": child_program_code,
            "cost": result.get("cost", float("inf")),
            "reward": reward,
        }
    )

# Save results
with open("rl_experiment_log.json", "w") as f:
    json.dump(EXPERIMENT_LOG, f, indent=2)

logging.info("RL training complete. Log saved to rl_experiment_log.json")
