# Main Python script
from src.database import database 
from src.evolve import apply_diff 

import src.llm as llm
import src.evaluator as evaluator
import src.prompt_sampler as prompt_sampler

if __name__ == '__main__':
    # Step 1
    parent_program, inspirations = database.sample()

    # Step 2
    prompt = prompt_sampler.build(parent_program, inspirations)
    
    # Step 3
    diff = llm.generate(prompt)

    # Step 4
    child_program = apply_diff(parent_program, diff)

    # Step 5
    results = evaluator.execute(child_program)

    # Step 6
    database.add(child_program, results)

    print('Hello, world!')