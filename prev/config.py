import os
from dotenv import load_dotenv
from pathlib import Path

# Force-load .env from project root
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

# === GROQ CONFIG ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL")

if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY not found. Check your .env file.")

if not GROQ_MODEL:
    raise RuntimeError("❌ GROQ_MODEL not found. Check your .env file.")
