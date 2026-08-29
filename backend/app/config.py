"""Central configuration. Every tunable lives in .env so that
local mode and (later) SaaS mode are the same code with different settings."""
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./swinglens.db")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# Optional cloud LLM (any OpenAI-compatible API; Groq free tier works well).
# Used only when LLM_PROVIDER=cloud. Without a key, the app still runs -
# narration falls back to deterministic templates and chat shows offline.
CLOUD_LLM_BASE_URL = os.getenv("CLOUD_LLM_BASE_URL", "https://api.groq.com/openai/v1")
CLOUD_LLM_API_KEY = os.getenv("CLOUD_LLM_API_KEY", "")
CLOUD_LLM_MODEL = os.getenv("CLOUD_LLM_MODEL", "llama-3.1-8b-instant")

# Demo mode for showcases/hackathons: seeds a ready-made account and shows
# a one-click "Try the demo" button on the login page.
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
DEMO_EMAIL = "demo@swinglens.app"
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "swingdemo123")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

JWT_ALGORITHM = "HS256"
