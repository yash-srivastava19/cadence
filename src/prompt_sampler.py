import re

# Global mutable instruction
INSTRUCTION_TEMPLATE = """
Your task is to modify this program to reduce the cost and increase efficiency.
Only modify code inside the START_BLOCK and END_BLOCK markers.
Do not repeat the same logic unless necessary.
Avoid markdown or explanation in your output.
Ensure the code is self-contained and executable.
"""

def update_instruction(new_instruction: str):
    """
    Updates the global instruction template used in prompts.
    """
    global INSTRUCTION_TEMPLATE
    INSTRUCTION_TEMPLATE = new_instruction

def extract_code_blocks(code: str, start_marker="### START_BLOCK", end_marker="### END_BLOCK"):
    """
    Extract code blocks that are between start and end markers.
    """
    pattern = re.compile(rf"{re.escape(start_marker)}\n([\s\S]*?)\n{re.escape(end_marker)}", re.MULTILINE)
    return [match.group(1).strip() for match in pattern.finditer(code)]

def build(parent_program, inspirations=None, last_diff=None, last_metric=None):
    """
    Constructs a prompt for the LLM to evolve a given program.

    Args:
        parent_program (tuple): (id, generation_number, parent_id, program_code, metric)
        inspirations (list): Optional list of child programs (same format)
        last_diff (str): Optional - last attempted diff
        last_metric (float): Optional - result of last diff

    Returns:
        str: Fully formed prompt string
    """
    parent_code = parent_program[3] if parent_program else ""
    parent_metric = parent_program[4] if parent_program else "N/A"
    block_count = len(extract_code_blocks(parent_code))

    prompt = f"""You are an expert Python programmer tasked with evolving a given program.

### PARENT PROGRAM (baseline):
{parent_code}

# Metric: {parent_metric}

"""

    if inspirations:
        prompt += "### INSPIRATION PROGRAMS (previous mutations):\n"
        for i, insp in enumerate(inspirations):
            prompt += f"## Inspiration #{i+1}\n{insp[3]}\n# Metric: {insp[4]}\n\n"

    if last_diff and last_metric is not None:
        prompt += f"""### LAST DIFF + METRIC
Diff applied:
{last_diff}

Resulting metric: {last_metric}

Please suggest a better variation.
"""

    prompt += f"""
### TASK:
{INSTRUCTION_TEMPLATE}

- There are {block_count} code block(s) to modify.
- Return exactly {block_count} updated blocks in the same order they appear.
- Each block must be formatted as:

### START_BLOCK
<your updated code>
### END_BLOCK

No commentary, no markdown, no extra text — only the code blocks.
"""

    return prompt.strip()
