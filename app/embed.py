"""
Embedding via Ollama nomic-embed-text (768 dimensions).
"""

from __future__ import annotations

import os

import httpx

OLLAMA_URL    = os.getenv("OLLAMA_URL",        "http://ollama.llm.svc.cluster.local:11434")
EMBED_MODEL   = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT = float(os.getenv("OLLAMA_EMBED_TIMEOUT", "30"))


async def embed(text: str) -> list[float]:
    """Return the embedding vector for *text*."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=EMBED_TIMEOUT,
        )
        r.raise_for_status()
    return r.json()["embedding"]
