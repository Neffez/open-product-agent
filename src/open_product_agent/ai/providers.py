from __future__ import annotations

from open_product_agent.ai.base import AIProvider
from open_product_agent.ai.ollama_provider import OllamaProvider
from open_product_agent.ai.openai_provider import OpenAIProvider


def create_provider(provider: str, *, model: str, temperature: float = 0) -> AIProvider:
    if provider == "openai":
        return OpenAIProvider(model=model, temperature=temperature)
    if provider == "ollama":
        return OllamaProvider(model=model, temperature=temperature)
    raise ValueError(f"Unsupported AI provider: {provider}")
