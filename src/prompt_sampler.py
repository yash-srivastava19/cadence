def build(parent_program, inspirations):
    """
    Constructs a prompt for an LLM given a parent program and a set of inspirations.

    Args:
        parent_program (tuple): (id, generation_number, parent_id, program_code, metric) or None if no parent found.
        inspirations (list): List of tuples, each representing a child program:
                             (id, generation_number, parent_id, program_code, metric)

    Returns:
        str: A prompt string for the LLM.
    """
    prompt = ""

    if parent_program:
        prompt += f"Parent Program:\n{parent_program[3]}\n\n"  # Assuming program_code is at index 3
    else:
        prompt += "No parent program found.\n\n"

    if inspirations:
        prompt += "Inspirations:\n"
        for inspiration in inspirations:
            prompt += f"{inspiration[3]}\n"  # Assuming program_code is at index 3
    else:
        prompt += "No inspirations found.\n"

    return prompt

### GPT-4o

import re

def extract_code_blocks(code: str, start_marker="### START_BLOCK", end_marker="### END_BLOCK"):
    """
    Extract code blocks that are between start and end markers.
    """
    pattern = re.compile(rf"{re.escape(start_marker)}\n([\s\S]*?)\n{re.escape(end_marker)}", re.MULTILINE)
    return [match.group(1).strip() for match in pattern.finditer(code)]

def build(parent_program, inspirations):
    """
    Constructs a prompt for an LLM given a parent program and a set of inspirations.

    Args:
        parent_program (tuple): (id, generation_number, parent_id, program_code, metric)
        inspirations (list): List of child programs with the same structure.

    Returns:
        str: A fully constructed prompt string for the LLM.
    """
    prompt = "You are an expert Python programmer tasked with evolving a given program.\n\n"

    # Add parent program
    if parent_program:
        prompt += "### PARENT PROGRAM (baseline):\n"
        prompt += parent_program[3] + "\n\n"
        prompt += f"# Metric: {parent_program[4]}\n\n"
    else:
        prompt += "No parent program found.\n\n"

    # Add inspiration programs (previous mutations)
    if inspirations:
        prompt += "### INSPIRATION PROGRAMS (previous mutations):\n"
        for i, insp in enumerate(inspirations):
            prompt += f"## Inspiration #{i+1}\n"
            prompt += insp[3] + "\n"
            prompt += f"# Metric: {insp[4]}\n\n"
    else:
        prompt += "No inspiration programs available.\n\n"

    # Instruction to generate new code
    prompt += (
    "### TASK:\n"
    "Your task is to modify this program to reduce the cost of the tour.\n\n"
    "Only modify code *inside the blocks marked* by:\n"
    "    ### START_BLOCK\n"
    "    ... code here ...\n"
    "    ### END_BLOCK\n\n"
    "You MUST output only replacement code blocks.\n"
    "- Each block should start with a single ### START_BLOCK line\n"
    "- Then plain Python code (no markdown, no backticks, no triple quotes)\n"
    "- Then a single ### END_BLOCK line\n"
    "- Do not repeat or nest the markers\n"
    "- Do not include any text or explanation outside these blocks\n\n"
    "Output as many blocks as exist in the parent program, in order.\n"
    "Each block must correspond 1-to-1 with a block in the parent code.\n"
    "Avoid copying the exact same structure or logic unless necessary.\n"
    "Try a different approach, optimization, or heuristic to reduce cost.\n"
    "Do not assume any import or library unless you explicitly include it.\n"
    "The code should run when passed to `exec()`, without relying on any outside context.\n"
    )

    return prompt
