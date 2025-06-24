import os
from dotenv import load_dotenv

def load_env():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set in .env file.")
    return api_key
