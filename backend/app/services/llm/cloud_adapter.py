"""OpenAI-compatible cloud adapter.

Works with any /chat/completions provider: Groq (free tier), OpenRouter,
Together, OpenAI, Google's OpenAI-compat endpoint... Selected only when
LLM_PROVIDER=cloud; local Ollama stays the default everywhere else.
"""
import httpx

from ... import config
from .base import LLMAdapter, LLMUnavailable

_HINT = ("Set CLOUD_LLM_API_KEY in the environment (Groq's free tier at "
         "console.groq.com is a zero-cost option), or switch LLM_PROVIDER back to ollama.")


class CloudAdapter(LLMAdapter):
    provider_name = "cloud"

    def chat(self, messages: list[dict]) -> str:
        if not config.CLOUD_LLM_API_KEY:
            raise LLMUnavailable("No cloud LLM key configured.", _HINT)
        try:
            resp = httpx.post(
                f"{config.CLOUD_LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.CLOUD_LLM_API_KEY}"},
                json={"model": config.CLOUD_LLM_MODEL, "messages": messages, "stream": False},
                timeout=120.0,
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Could not reach {config.CLOUD_LLM_BASE_URL}.", _HINT) from exc
        if resp.status_code == 401:
            raise LLMUnavailable("Cloud LLM key was rejected (401).", _HINT)
        if resp.status_code != 200:
            raise LLMUnavailable(f"Cloud LLM returned HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise LLMUnavailable("Cloud LLM returned an unexpected response shape.") from exc

    def status(self) -> dict:
        if not config.CLOUD_LLM_API_KEY:
            return {"online": False, "model": config.CLOUD_LLM_MODEL, "detail": _HINT}
        return {"online": True, "model": config.CLOUD_LLM_MODEL,
                "model_installed": True, "detail": f"Cloud LLM via {config.CLOUD_LLM_BASE_URL}"}
