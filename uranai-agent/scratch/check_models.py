import os
import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

models = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3-opus-20240229"
]

for model in models:
    try:
        print(f"Testing {model}...")
        client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        print(f"SUCCESS: {model}")
        break
    except Exception as e:
        print(f"FAILED: {model} - {e}")
