import src.config
from src.llm.base import BaseProvider
from src.llm.providers.gemini import GeminiProvider
from src.llm.providers.ollama import OllamaProvider


def get_llm_provider() -> BaseProvider:
    """Returns the configured LLM provider instance."""
    provider_name = src.config.LLM_PROVIDER.lower()

    if provider_name == "gemini":
        if not src.config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
        return GeminiProvider(api_key=src.config.GEMINI_API_KEY)
    elif provider_name == "ollama":
        return OllamaProvider(host=src.config.OLLAMA_HOST, model=src.config.OLLAMA_MODEL)
    else:
        raise ValueError(f"Unknown LLM provider configured: {src.config.LLM_PROVIDER}")
