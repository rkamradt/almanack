"""
Vector similarity retrieval from almanack.sayings.
"""

from __future__ import annotations

import os

import asyncpg

from app.embed import embed

TOP_K           = int(float(os.getenv("RETRIEVAL_TOP_K",           "5")))
MIN_SIMILARITY  = float(os.getenv("RETRIEVAL_MIN_SIMILARITY",       "0.35"))


def filter_by_threshold(
    sayings: list[dict], threshold: float = MIN_SIMILARITY
) -> list[dict]:
    """Return only sayings whose similarity meets *threshold*."""
    return [s for s in sayings if s["similarity"] >= threshold]


async def retrieve(question: str, pool: asyncpg.Pool) -> list[dict]:
    """
    Embed *question*, query the HNSW index, return top-K results above
    the minimum similarity threshold.

    Each result dict: {id, text, year, source, line_ref, similarity}
    """
    query_vec = await embed(question)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, text, year, source, line_ref,
                   (1 - (embedding <=> $1::vector)) AS similarity
            FROM almanack.sayings
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            query_vec,
            TOP_K,
        )

    results = [
        {
            "id":         row["id"],
            "text":       row["text"],
            "year":       row["year"],
            "source":     row["source"],
            "line_ref":   row["line_ref"],
            "similarity": float(row["similarity"]),
        }
        for row in rows
    ]

    return filter_by_threshold(results, threshold=MIN_SIMILARITY)
