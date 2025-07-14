import textwrap
from src.llm import generate_lessons  # your existing LLM interface

META_PROMPT_TEMPLATE = """
You are analyzing a sequence of attempted improvements to a program designed to solve a complex optimization problem.

Each attempt includes:
- The modified code
- The associated performance cost
- Whether the solution was feasible (1.0) or not (0.0)

Your task is to extract a general lesson statement that could guide the next generation of solutions. This lesson should:
- Identify what strategies were attempted and what didn’t work
- Suggest a new direction or adjustment in approach
- Be applicable to the same problem if attempted again

Only output a single lesson statement. Do not explain, summarize, or wrap in markdown.

=== HISTORY ===
{history}

=== END ===

Lesson:
"""


def format_generation_entry(entry, feedback=None):
    code = textwrap.indent(entry.get("program_code", "").strip(), "    ")
    fb_line = (
        f"# Feedback from prior lesson: {feedback}"
        if feedback
        else "# Feedback: (none)"
    )
    return f"""## Generation {entry["generation"]}
Cost: {entry["cost"]} | Feasibility: {entry["feasibility"]}
{fb_line}
Code:
{code}
"""


def get_lesson_from_history(logs, N=2, previous_lesson=None):
    recent = sorted(logs, key=lambda x: x["generation"], reverse=True)
    selected = [e for e in recent if "program_code" in e][:N]
    if not selected:
        return None

    history = "\n\n".join(
        format_generation_entry(e, feedback=previous_lesson) for e in selected
    )
    prompt = META_PROMPT_TEMPLATE.format(history=history)
    # Send to LLM
    try:
        lesson_statement = generate_lessons(prompt)
        # history_with_feedback = "\n\n".join(format_generation_entry(e, lesson=lesson_statement) for e in selected)
        return lesson_statement.strip()
    except Exception as e:
        print(f"[Meta] Failed to generate lesson: {e}")
        return None
