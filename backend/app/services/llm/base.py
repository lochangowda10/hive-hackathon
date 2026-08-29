"""LLM adapter contract.

Every part of the platform talks to AI through this interface only.
Local mode = OllamaAdapter. SaaS mode = a cloud adapter implementing
the same two methods. Nothing else in the codebase changes.
"""
from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    provider_name: str = "unknown"

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
        Returns the assistant's reply text. Raises LLMUnavailable on failure."""

    @abstractmethod
    def status(self) -> dict:
        """Returns {"online": bool, "model": str, "detail": str}."""


class LLMUnavailable(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


def get_llm() -> LLMAdapter:
    from ...config import LLM_PROVIDER

    if LLM_PROVIDER == "ollama":
        from .ollama_adapter import OllamaAdapter

        return OllamaAdapter()
    if LLM_PROVIDER == "cloud":
        from .cloud_adapter import CloudAdapter

        return CloudAdapter()
    raise LLMUnavailable(
        f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'.",
        hint="Set LLM_PROVIDER=ollama (local) or cloud (Groq/OpenAI-compatible) in .env.",
    )
