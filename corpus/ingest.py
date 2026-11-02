"""
One-time ingestion script: parse corpus → embed with nomic-embed-text → load to DB.

Usage (from inside the running pod or a one-shot Job):
    python -m corpus.ingest

Environment vars (same as the app):
    DB_URL       postgresql://almanack_user:pass@host:5432/almanack
    OLLAMA_URL   http://ollama.llm.svc.cluster.local:11434

Idempotent: skips records that are already in the database (matched by text).
Writes an ingestion report to stdout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

import asyncpg
import httpx
import pgvector.asyncpg

from corpus.parse import parse_file

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_URL    = os.environ["DB_URL"]
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama.llm.svc.cluster.local:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
VECTOR_DIM  = 768


async def get_embedding(client: httpx.AsyncClient, text: str) -> list[float]:
    r = await client.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embedding"]


async def ensure_schema(conn: asyncpg.Connection) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.execute("CREATE SCHEMA IF NOT EXISTS almanack")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS almanack.sayings (
            id       SERIAL PRIMARY KEY,
            text     TEXT        NOT NULL,
            modern   TEXT        NOT NULL,
            year     SMALLINT,
            source   VARCHAR(60),
            line_ref VARCHAR(30),
            embedding vector(768)
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS sayings_embedding_idx
            ON almanack.sayings USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """)


async def main() -> None:
    corpus_dir = Path(__file__).parent / "raw"
    txt_files  = sorted(corpus_dir.glob("*.txt"))
    if not txt_files:
        log.error("No .txt files found in %s", corpus_dir)
        sys.exit(1)

    # Parse all files
    all_sayings: list[dict] = []
    for f in txt_files:
        parsed = parse_file(f)
        log.info("%s → %d sayings parsed", f.name, len(parsed))
        all_sayings.extend(parsed)

    # Deduplicate across files (by lowercased text)
    seen: set[str] = set()
    unique: list[dict] = []
    duplicates = 0
    for s in all_sayings:
        key = s["text"].lower().strip()
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
            unique.append(s)

    log.info("Total parsed: %d  Duplicates merged: %d  Unique: %d",
             len(all_sayings), duplicates, len(unique))

    conn = await asyncpg.connect(DB_URL)
    await pgvector.asyncpg.register_vector(conn)

    try:
        await ensure_schema(conn)

        # Find already-ingested texts
        existing = {
            row["text"]
            for row in await conn.fetch("SELECT text FROM almanack.sayings")
        }
        to_ingest = [s for s in unique if s["text"] not in existing]
        log.info("Already in DB: %d  To ingest: %d", len(existing), len(to_ingest))

        if not to_ingest:
            log.info("Nothing new to ingest.")
            _print_report(unique, duplicates, skipped=len(unique) - len(to_ingest))
            return

        async with httpx.AsyncClient() as client:
            for i, saying in enumerate(to_ingest, start=1):
                log.info("[%d/%d] Embedding: %.60s…", i, len(to_ingest), saying["text"])
                embedding = await get_embedding(client, saying["modern"])
                await conn.execute(
                    """
                    INSERT INTO almanack.sayings (text, modern, year, source, line_ref, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    saying["text"],
                    saying["modern"],
                    saying["year"],
                    saying["source"],
                    saying["line_ref"],
                    embedding,
                )

        log.info("Ingestion complete.")
    finally:
        await conn.close()

    _print_report(unique, duplicates, skipped=len(unique) - len(to_ingest))


def _print_report(unique: list[dict], duplicates: int, skipped: int) -> None:
    report = {
        "total_unique_sayings": len(unique),
        "duplicates_merged":    duplicates,
        "already_in_db":        skipped,
        "newly_ingested":       len(unique) - skipped,
        "sources":              dict(Counter(s["source"] for s in unique)),
        "examples": [s["text"] for s in unique[:5]],
        "examples_modern": [s["modern"] for s in unique[:5]],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
