"""
Database connection pool and schema bootstrap.
Uses asyncpg + pgvector.
"""

from __future__ import annotations

import os

import asyncpg
import pgvector.asyncpg

DB_URL = os.environ.get("DB_URL", "postgresql://almanack_user:almanack_pass@postgresql.postgresql.svc.cluster.local:5432/almanack")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=5,
            init=_init_conn,
        )
    return _pool


async def _init_conn(conn: asyncpg.Connection) -> None:
    await pgvector.asyncpg.register_vector(conn)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def bootstrap_schema(pool: asyncpg.Pool) -> None:
    """Create schema, table, and index if they don't exist."""
    async with pool.acquire() as conn:
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


async def count_sayings(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM almanack.sayings")
