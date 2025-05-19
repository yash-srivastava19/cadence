def build():
    pass

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