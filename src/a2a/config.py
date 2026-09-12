"""Configuration helpers loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Walk up from this file (src/a2a/config.py) to find the project .env.
    here = Path(__file__).resolve().parent  # .../a2a/src/a2a
    for candidate in (here.parents[1], here.parents[2], here.parents[0]):
        env_path = candidate / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=True)
            break
except Exception:  # pragma: no cover - dotenv optional at runtime
    pass


@dataclass(frozen=True)
class Settings:
    model_provider: str = os.getenv("MODEL_PROVIDER", "ollama")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    a2a_host: str = os.getenv("A2A_HOST", "127.0.0.1")
    a2a_port_base: int = int(os.getenv("A2A_PORT_BASE", "8000"))

    # --- Agentic router (lower = small/fast, higher = large/capable) ---
    lower_vllm_base_url: str = os.getenv("LOWER_VLLM_BASE_URL", "http://localhost:11434/v1")
    lower_model: str = os.getenv("LOWER_MODEL", "deepseek-v4-flash:cloud")
    higher_vllm_base_url: str = os.getenv("HIGHER_VLLM_BASE_URL", "http://localhost:11434/v1")
    higher_model: str = os.getenv("HIGHER_MODEL", "glm-5.2:cloud")
    vllm_api_key: str = os.getenv("VLLM_API_KEY", "EMPTY")
    router_lower_threshold: float = float(os.getenv("ROUTER_LOWER_THRESHOLD", "0.15"))
    router_higher_threshold: float = float(os.getenv("ROUTER_HIGHER_THRESHOLD", "0.45"))
    router_classifier_band: float = float(os.getenv("ROUTER_CLASSIFIER_BAND", "0.05"))


settings = Settings()