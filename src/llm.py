def generate():
    pass

import os
import cohere
import dotenv

dotenv.load_dotenv()
CO_API_KEY = os.getenv("CO_API_KEY")


co = cohere.ClientV2(CO_API_KEY)

response = co.chat(
    model="command-a-03-2025",
    messages=[{"role": "user", "content": "hello world!"}],
)

print(response.message.content[0].text)