from google import genai
import os
import dotenv

dotenv.load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


def mutate_instruction(base_instruction: str) -> str:
    """
    Sends a meta-prompt to improve the instruction text for the next generation.
    """
    meta_prompt = f"""You are modifying instructions for an AI code optimizer.

The current instruction is:

\"\"\"{base_instruction}\"\"\"

Please rewrite it to help the model be more creative, more effective at reducing cost, and less repetitive.
Keep the instruction concise and return only the new instruction block, nothing else."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=meta_prompt,
        )
        return response.text

    except Exception as e:
        print(f"[LLM Error in Meta Prompt Generation] {e}")
        return base_instruction


def generate(prompt):
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return extract_valid_blocks(response.text)

    except Exception as e:
        print(f"[LLM Error in Program Evolution] {e}")
        return []


def extract_valid_blocks(text):
    """
    Extracts all code snippets between ### START_BLOCK and ### END_BLOCK.
    """
    import re

    pattern = r"### START_BLOCK\n(.*?)\n### END_BLOCK"
    return re.findall(pattern, text, re.DOTALL)
