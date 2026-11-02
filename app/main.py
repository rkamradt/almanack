"""
Poor Richard's Engineering Almanack — FastAPI application.

Endpoints:
    GET  /health        liveness / readiness probe
    GET  /random        random saying of the day
    POST /ask           RAG answer in Franklin's voice
    GET  /              serves the colonial almanac SPA
"""

from __future__ import annotations

import logging
import random

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded

from app import db as database
from app import generate, retrieve
from app.limiter import RATE_LIMIT_STRING, check_and_charge, current_spend, limiter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Poor Richard's Engineering Almanack", version="0.1.0")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse({"detail": "Too many requests — even Poor Richard rests his quill."}, status_code=429)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    pool = await database.get_pool()
    await database.bootstrap_schema(pool)
    count = await database.count_sayings(pool)
    if count == 0:
        log.warning(
            "No sayings found in DB. Run 'python -m corpus.ingest' to populate."
        )
    else:
        log.info("Almanack ready with %d sayings.", count)


@app.on_event("shutdown")
async def shutdown() -> None:
    await database.close_pool()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_pool():
    return await database.get_pool()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class QuestionRequest(BaseModel):
    question: str

    def validate_question(self) -> None:
        q = self.question.strip()
        if not q:
            raise HTTPException(422, "question must not be empty")
        if len(q) > 500:
            raise HTTPException(422, "question must be 500 characters or fewer")


class SayingOut(BaseModel):
    text: str
    year: int | None
    source: str | None
    similarity: float


class AskResponse(BaseModel):
    answer: str
    sayings: list[SayingOut]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(pool=Depends(get_pool)) -> dict:
    count = await database.count_sayings(pool)
    return {
        "status": "ok",
        "sayings_loaded": count,
        "daily_spend_usd": round(current_spend(), 4),
    }


@app.get("/random", response_model=SayingOut | dict)
async def random_saying(pool=Depends(get_pool)):
    count = await database.count_sayings(pool)
    if count == 0:
        raise HTTPException(503, "No sayings loaded yet. Run corpus ingestion first.")

    offset = random.randint(0, count - 1)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT text, year, source FROM almanack.sayings OFFSET $1 LIMIT 1",
            offset,
        )
    return {"text": row["text"], "year": row["year"], "source": row["source"], "similarity": 1.0}


@app.post("/ask", response_model=AskResponse)
@limiter.limit(RATE_LIMIT_STRING)
async def ask(
    body: QuestionRequest,
    request: Request,  # required by slowapi
    pool=Depends(get_pool),
):
    body.validate_question()

    if not check_and_charge():
        raise HTTPException(
            429,
            "Poor Richard's daily counsel hath been exhausted. "
            "Return on the morrow for more wisdom.",
        )

    sayings = await retrieve.retrieve(body.question, pool)

    answer_text = await generate.answer(body.question, sayings)

    return AskResponse(
        answer=answer_text,
        sayings=[
            SayingOut(
                text=s["text"],
                year=s.get("year"),
                source=s.get("source"),
                similarity=s["similarity"],
            )
            for s in sayings
        ],
    )


# ---------------------------------------------------------------------------
# Static SPA — registered last so API routes take precedence
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="public", html=True), name="static")
