import os

from dotenv import load_dotenv

load_dotenv()

ZAI_API_KEY = os.getenv("ZAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
