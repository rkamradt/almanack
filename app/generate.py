"""
LLM answer generation with quote verification.

Flow:
1. Build prompt with retrieved sayings.
2. Call Anthropic (default) or Ollama (LLM_PROVIDER=ollama).
3. Extract all double-quoted strings from the answer.
4. Verify each appears verbatim in at least one retrieved saying's text.
5. On failure → regenerate once with a stronger instruction.
6. On second failure → return the raw sayings and a fallback message.
"""

from __future__ import annotations

import os
import re

import httpx

LLM_PROVIDER   = os.getenv("LLM_PROVIDER",    "anthropic")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL",  "claude-haiku-4-5-20251001")
OLLAMA_URL      = os.getenv("OLLAMA_URL",        "http://ollama.llm.svc.cluster.local:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",      "llama3.2:3b-instruct-q4_K_M")
LLM_TIMEOUT     = float(os.getenv("LLM_TIMEOUT", "60"))

_SYSTEM = (
    "You are Poor Richard (Benjamin Franklin), answering a software-engineering "
    "question. Speak in a lightly period voice but be clearly understood by modern "
    "readers. You MUST only quote sayings from the list provided below, verbatim, "
    "word-for-word, in double quotation marks. Never invent or attribute to Poor "
    "Richard any saying not in the list. For each quoted saying, note the year if "
    "present. If no retrieved saying is relevant, say so in character: "
    "'Poor Richard has no proverb for that, but I would counsel thee thus…' "
    "and offer general wisdom without fabricating a quote."
)

_STRICT_SUFFIX = (
    "\n\nCRITICAL: Every string you place in double quotation marks MUST match "
    "exactly—character for character—one of the sayings in the list above. "
    "Do not paraphrase. Do not combine. Do not invent."
)

_FALLBACK_INTRO = (
    "Poor Richard's quill must be cautious, for I cannot verify mine own words "
    "in this matter. Here, instead, are the proverbs most pertinent to thy question:"
)


# ---------------------------------------------------------------------------
# Quote extraction & verification
# ---------------------------------------------------------------------------

def extract_quotes(text: str) -> list[str]:
    """Return all double-quoted substrings of at least 10 characters."""
    return re.findall(r'"([^"]{10,})"', text)


def verify_quotes(answer: str, sayings: list[dict]) -> bool:
    """
    Return True if every quoted string in *answer* appears verbatim as a
    substring of at least one retrieved saying's text field.
    """
    quotes = extract_quotes(answer)
    if not quotes:
        return True  # no quotes to verify
    all_texts = [s["text"] for s in sayings]
    for q in quotes:
        if not any(q in t for t in all_texts):
            return False
    return True


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def _build_user_prompt(question: str, sayings: list[dict], strict: bool = False) -> str:
    lines = ["Retrieved Poor Richard's sayings (use ONLY these, verbatim):\n"]
    for s in sayings:
        year_note = f" [{s['year']}]" if s.get("year") else ""
        lines.append(f'  • "{s["text"]}"{year_note}')
    lines.append(f"\nSoftware-engineering question: {question}")
    if strict:
        lines.append(_STRICT_SUFFIX)
    return "\n".join(lines)


async def _call_anthropic(system: str, user: str) -> str:
    import anthropic  # imported lazily so tests don't need the key

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)
    msg = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


async def _call_ollama(system: str, user: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            },
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
    return r.json()["message"]["content"]


async def _generate(system: str, user: str) -> str:
    if LLM_PROVIDER == "ollama":
        return await _call_ollama(system, user)
    return await _call_anthropic(system, user)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def answer(question: str, sayings: list[dict]) -> str:
    """
    Generate a Poor Richard answer grounded in *sayings*.

    Returns the answer string. If quote verification fails twice, returns
    a fallback that lists the sayings plainly.
    """
    if not sayings:
        return (
            "Ah, friend, Poor Richard has no proverb that fits thy question precisely. "
            "I counsel thee to seek wisdom from those who have walked that road before thee, "
            "for 'experience keeps a dear school, but fools will learn in no other.'"
        )

    user1 = _build_user_prompt(question, sayings, strict=False)
    result = await _generate(_SYSTEM, user1)

    if verify_quotes(result, sayings):
        return result

    # First attempt failed verification — try with stricter prompt
    user2 = _build_user_prompt(question, sayings, strict=True)
    result2 = await _generate(_SYSTEM, user2)

    if verify_quotes(result2, sayings):
        return result2

    # Both attempts failed — return fallback
    lines = [_FALLBACK_INTRO, ""]
    for s in sayings:
        year_note = f" ({s['year']})" if s.get("year") else ""
        lines.append(f'"{s["text"]}"{year_note}')
    return "\n\n".join(lines)
