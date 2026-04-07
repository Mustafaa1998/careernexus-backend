import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_env_list(key: str):
    try:
        return json.loads(os.getenv(key, "[]"))
    except json.JSONDecodeError:
        return []

class Settings:
    PORT = int(os.getenv("PORT", 7000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    DATABASE_URL = os.getenv("DATABASE_URL")
    JOB_BASE = os.getenv("JOB_BASE")
    UNI_REC_BASE = os.getenv("UNI_REC_BASE")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    ALLOW_ORIGINS = get_env_list("ALLOW_ORIGINS")

settings = Settings()
