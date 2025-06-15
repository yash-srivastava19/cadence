from google import genai
import os
import dotenv

dotenv.load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key = GEMINI_API_KEY)

def generate(prompt):
    try:
        response = client.models.generate_content(
            model = "gemini-2.0-flash",
            contents = prompt,
        )
        return extract_valid_blocks(response.text)

    except Exception as e:
        print(f"[LLM Error] {e}")
        return []


def extract_valid_blocks(text):
    """
    Extracts all code snippets between ### START_BLOCK and ### END_BLOCK.
    """
    import re
    pattern = r"### START_BLOCK\n(.*?)\n### END_BLOCK"
    return re.findall(pattern, text, re.DOTALL)
