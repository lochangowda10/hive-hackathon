import httpx

from ...config import OLLAMA_BASE_URL, OLLAMA_MODEL
from .base import LLMAdapter, LLMUnavailable

_START_HINT = (
    "Make sure the Ollama app is running on this computer, then pull the model with: "
    f"ollama pull {OLLAMA_MODEL}"
)


class OllamaAdapter(LLMAdapter):
    provider_name = "ollama"

    def chat(self, messages: list[dict]) -> str:
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
                timeout=180.0,
            )
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Could not reach Ollama at {OLLAMA_BASE_URL}.", _START_HINT) from exc
        if resp.status_code == 404:
            raise LLMUnavailable(
                f"Model '{OLLAMA_MODEL}' is not installed in Ollama.", _START_HINT
            )
        if resp.status_code != 200:
            raise LLMUnavailable(f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()

    def status(self) -> dict:
        try:
            resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            resp.raise_for_status()
        except httpx.HTTPError:
            return {"online": False, "model": OLLAMA_MODEL, "detail": _START_HINT}
        installed = [m.get("name", "") for m in resp.json().get("models", [])]
        available = any(name.startswith(OLLAMA_MODEL.split(":")[0]) for name in installed)
        return {
            "online": True,
            "model": OLLAMA_MODEL,
            "model_installed": available,
            "installed_models": installed,
            "detail": "Ready." if available else f"Run: ollama pull {OLLAMA_MODEL}",
        }
