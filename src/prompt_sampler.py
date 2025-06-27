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


def extract_code_blocks(
    code: str, start_marker="### START_BLOCK", end_marker="### END_BLOCK"
):
    """
    Extract code blocks that are between start and end markers.
    """
    pattern = re.compile(
        rf"{re.escape(start_marker)}\n([\s\S]*?)\n{re.escape(end_marker)}", re.MULTILINE
    )
    return [match.group(1).strip() for match in pattern.finditer(code)]


def build(parent_program, inspirations):
    """
    Builds a structured prompt to encourage novelty and heuristics.
    """
    prompt = """You are an expert engineer tasked with improving a Python program that solves a real-world optimization problem.

The current implementation may be functional, but there is significant room for improvement in:
- efficiency
- solution quality
- clarity and generalization

Your task is to generate a modified version of the code that:
- explores a new strategy (not the same as previous attempts)
- avoids brute-force if possible
- uses simple heuristics, local search, or rule-based logic
- reduces cost and improves reliability over multiple test cases

Only change code inside the blocks marked by:
    ### START_BLOCK
    ...code...
    ### END_BLOCK

You MUST output the same number of blocks as in the parent program. Do NOT include anything else.
"""

    # Add the current (parent) baseline
    prompt += "\n### CURRENT BASELINE SOLUTION:\n"
    prompt += parent_program[3] + "\n"
    prompt += f"# Baseline cost: {parent_program[4]}\n"

    # Add inspiration programs if any
    if inspirations:
        prompt += "\n### PREVIOUS ATTEMPTS:\n"
        for i, insp in enumerate(inspirations):
            prompt += f"\n## Attempt #{i + 1} (Cost: {insp[4]})\n"
            prompt += insp[3] + "\n"

    # Final reminder
    prompt += "\n### INSTRUCTIONS:\n"
    prompt += "- Try a fundamentally different idea from previous versions.\n"
    prompt += "- Avoid copying structure unless necessary.\n"
    prompt += "- Do not include extra explanation or comments.\n"
    prompt += "- Output ONLY valid Python code blocks between the markers.\n"

    return prompt
