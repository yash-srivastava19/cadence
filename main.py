import logging
import json

from src.database import sample, add, get_best_program
from src.evaluator import execute
from src.evolve import apply_diff
from src.prompt_sampler import build, update_instruction, INSTRUCTION_TEMPLATE
from src.llm import generate, mutate_instruction

logging.basicConfig(level=logging.INFO)

NUM_GENERATIONS = 6
ELITISM_INTERVAL = 5
META_PROMPT_EDIT_INTERVAL = 2
EXPERIMENT_LOG = []

if __name__ == '__main__':
    generation = 1
    while generation <= NUM_GENERATIONS:
        logging.info(f"=== Generation {generation} ===")

        if generation > 0 and generation % META_PROMPT_EDIT_INTERVAL == 0:
            logging.info("Evolving meta prompt...")
            new_instruction = mutate_instruction(INSTRUCTION_TEMPLATE)
            update_instruction(new_instruction)
            logging.info(f"Updated instruction:\n{new_instruction}")

        # Step 1: Select parent program (with elitism every ELITISM_INTERVAL generations)
        if generation > 0 and generation % ELITISM_INTERVAL == 0:
            parent_program = get_best_program()
            inspirations = []  # Best program may not have children
            if not parent_program:
                logging.warning("No best program found. Skipping generation.")
                generation += 1
                continue
            logging.info(f"Elitism triggered. Using best program ID: {parent_program[0]} (Metric: {parent_program[4]:.4f})")
        else:
            parent_program, inspirations = sample(generation_number=generation)
            if not parent_program:
                logging.warning("No parent program found. Skipping generation.")
                generation += 1
                continue
            logging.info(f"Sampled parent program ID: {parent_program[0]}")

        # Step 2: Build prompt
        prompt = build(parent_program, inspirations)

        # Step 3: Generate diffs
        try:
            diffs = generate(prompt)
        except Exception as e:
            logging.error(f"LLM generation failed: {e}")
            break

        # Step 4: Apply diffs
        child_program_code = apply_diff(parent_program[3], diffs)

        # Step 5: Evaluate
        print(child_program_code)
        metric = execute(child_program_code)
        if "error" in metric:
            logging.error(f"Evaluation failed: {metric['error']}")
            continue
        logging.info(f"Evaluation metric for child: {metric['cost']:.4f}")

        # Step 6: Store in DB
        add(
            parent_id=parent_program[0],
            program_code=child_program_code,
            metric=metric['cost'],
            diff='\n\n'.join(diffs),
            prompt=prompt
        )

        # Step 7: Log experiment
        EXPERIMENT_LOG.append({
            "generation": generation + 1,
            "parent_id": parent_program[0],
            "metric": metric,
        })

        generation += 1
    with open("experiment_log.json", "w") as f:
        json.dump(EXPERIMENT_LOG, f, indent=2)

    logging.info("Experiment complete. Log saved to experiment_log.json")
