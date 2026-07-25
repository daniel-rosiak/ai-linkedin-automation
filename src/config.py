import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env if it exists
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID_STR = os.getenv("ALLOWED_CHAT_ID")
ALLOWED_CHAT_ID = None

if ALLOWED_CHAT_ID_STR:
    try:
        ALLOWED_CHAT_ID = int(ALLOWED_CHAT_ID_STR)
    except ValueError:
        pass

# LLM Settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Storage Settings
DATABASE_PATH = os.getenv("DATABASE_PATH", "history.db")
POSTS_DIR = os.getenv("POSTS_DIR", "./posts")

# Create directories if they don't exist
os.makedirs(POSTS_DIR, exist_ok=True)


def validate_config():
    """Validates that critical configurations are present."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set.")
    if ALLOWED_CHAT_ID is None:
        errors.append("ALLOWED_CHAT_ID is not set or is invalid (must be an integer).")

    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required when LLM_PROVIDER is set to 'gemini'.")
    elif LLM_PROVIDER == "ollama":
        if not OLLAMA_HOST:
            errors.append("OLLAMA_HOST is required when LLM_PROVIDER is set to 'ollama'.")
    else:
        errors.append(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Must be 'gemini' or 'ollama'.")

    return errors
