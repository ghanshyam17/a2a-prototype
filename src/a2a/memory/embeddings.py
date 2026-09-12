"""Embedding utilities backed by Ollama.

A tiny deterministic fallback is used when the Ollama server is unreachable so
the prototype can still run offline. The fallback is NOT suitable for production
semantic search but keeps the demo functional.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

import numpy as np

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Protocol any embedder must satisfy."""

    def embed(self, text: str) -> list[float]: ...


def _normalize(vec: list[float]) -> list[float]:
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return vec
    return (arr / norm).tolist()


class HashingEmbedder:
    """Deterministic lightweight embedder used as an offline fallback."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in text.lower().split():
            h = hash(tok) % self.dim
            vec[h] += 1.0
        return _normalize(vec.tolist())


class OllamaEmbedder:
    """Embedder that calls a local Ollama server via HTTP."""

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client: httpx.Client | None = None

    def embed(self, text: str) -> list[float]:
        try:
            import httpx

            if self._client is None:
                self._client = httpx.Client(timeout=10.0)
            resp = self._client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embeddings", data.get("embedding"))
            return _normalize(emb[0] if isinstance(emb, list) and emb and isinstance(emb[0], list) else emb)
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Ollama embed failed (%s); using hashing fallback.", exc)
            return HashingEmbedder().embed(text)


def default_embedder() -> Embedder:
    from a2a.config import settings

    if settings.model_provider == "ollama":
        return OllamaEmbedder(settings.ollama_embed_model, settings.ollama_base_url)
    return HashingEmbedder()