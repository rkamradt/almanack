"""
Parse Poor Richard's sayings from a Project Gutenberg plain-text file.

Strips the Gutenberg header/footer, then extracts every double-quoted string
that looks like a standalone saying (10–400 chars, not a title or footnote).
Produces one record per saying:
    text    – original wording, verbatim
    modern  – lightly modernised spelling only
    year    – None (Way to Wealth doesn't carry per-saying year attribution)
    source  – filename stem
    line_ref – "q<N>" (Nth quoted string extracted)
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Moderniser – spelling only; never changes word meaning
# ---------------------------------------------------------------------------

_MODERN = [
    (r"\bHath\b",       "Has"),
    (r"\bhath\b",       "has"),
    (r"\bDoth\b",       "Does"),
    (r"\bdoth\b",       "does"),
    (r"\bDost\b",       "Do"),
    (r"\bdost\b",       "do"),
    (r"\bWilt\b",       "Will"),
    (r"\bwilt\b",       "will"),
    (r"\bArt\b",        "Are"),    # "thou art" form
    (r"\bart\b",        "are"),
    (r"\bThou\b",       "You"),
    (r"\bthou\b",       "you"),
    (r"\bThee\b",       "You"),
    (r"\bthee\b",       "you"),
    (r"\bThy\b",        "Your"),
    (r"\bthy\b",        "your"),
    (r"\bThyself\b",    "Yourself"),
    (r"\bthyself\b",    "yourself"),
    (r"\bYe\b",         "You"),
    (r"\bye\b",         "you"),
    (r"'Tis\b",         "It is"),
    (r"'tis\b",         "it is"),
    (r"(\w+)'d\b",      lambda m: m.group(1) + "ed"),
    (r"\bere\b",        "before"),
    (r"\bnor\b",        "nor"),    # unchanged – keep
]

_compiled = [(re.compile(pat), repl) for pat, repl in _MODERN]


def modernize(text: str) -> str:
    t = text
    for pattern, repl in _compiled:
        if callable(repl):
            t = pattern.sub(repl, t)
        else:
            t = pattern.sub(repl, t)
    return t


# ---------------------------------------------------------------------------
# Gutenberg strip
# ---------------------------------------------------------------------------

_START = re.compile(r"\*\*\* START OF THE PROJECT GUTENBERG EBOOK[^\*]*\*\*\*", re.IGNORECASE)
_END   = re.compile(r"\*\*\* END OF THE PROJECT GUTENBERG EBOOK",               re.IGNORECASE)


def strip_gutenberg(raw: str) -> str:
    m = _START.search(raw)
    body = raw[m.end():] if m else raw
    m = _END.search(body)
    body = body[: m.start()] if m else body
    return body


# ---------------------------------------------------------------------------
# Saying extractor
# ---------------------------------------------------------------------------

# Illustration captions and publisher boilerplate to ignore
_SKIP_RE = re.compile(
    r"(Published by|Illustration|W\. Darton|Printed by|Holborn|FINIS|"
    r"Just published|Repository|ebook|Project Gutenberg)",
    re.IGNORECASE,
)


def _clean(s: str) -> str:
    """Collapse whitespace, strip surrounding punctuation artefacts."""
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(",;:.")
    return s


def parse_sayings(raw: str, source: str = "unknown") -> list[dict]:
    """
    Extract sayings from a Gutenberg plain-text file.

    Returns list of dicts: {text, modern, year, source, line_ref}
    """
    body = strip_gutenberg(raw)

    # Remove [Illustration ...] markers
    body = re.sub(r"\[Illustration[^\]]*\]", " ", body)

    # Extract all double-quoted substrings (greedy across newlines)
    raw_quotes = re.findall(r'"([^"]{10,400})"', body, re.DOTALL)

    seen: set[str] = set()
    records: list[dict] = []

    for idx, q in enumerate(raw_quotes, start=1):
        text = _clean(q)

        # Skip very short or clearly non-saying fragments
        if len(text) < 12:
            continue
        if _SKIP_RE.search(text):
            continue
        # Skip if it's mostly numbers/punctuation
        alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
        if alpha_ratio < 0.4:
            continue

        key = re.sub(r"\s+", " ", text.lower())
        if key in seen:
            continue
        seen.add(key)

        records.append(
            {
                "text":     text,
                "modern":   modernize(text),
                "year":     None,
                "source":   source,
                "line_ref": f"q{idx}",
            }
        )

    return records


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

def parse_file(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return parse_sayings(raw, source=path.stem)


if __name__ == "__main__":
    import json
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).parent / "raw" / "way-to-wealth-43855.txt"
    )
    sayings = parse_file(target)
    print(json.dumps(sayings, indent=2))
    print(f"\nTotal: {len(sayings)} sayings", file=sys.stderr)
