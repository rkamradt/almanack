"""
Unit tests for quote extraction and verification (app/generate.py).

The quote-verification step is the anti-hallucination guardrail:
it checks that every double-quoted string in the LLM's answer appears
verbatim in the retrieved sayings. A fabricated quote must be rejected.
"""

import pytest

from app.generate import extract_quotes, verify_quotes

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REAL_SAYING = "Early to bed, and early to rise, makes a man healthy, wealthy, and wise"
REAL_SAYING_2 = "Lost time is never found again"

SAYINGS = [
    {"text": REAL_SAYING,   "year": 1735},
    {"text": REAL_SAYING_2, "year": 1748},
]

# ---------------------------------------------------------------------------
# extract_quotes
# ---------------------------------------------------------------------------

def test_extract_single_quote():
    answer = f'Poor Richard counsels thee: "{REAL_SAYING}"'
    quotes = extract_quotes(answer)
    assert quotes == [REAL_SAYING]


def test_extract_multiple_quotes():
    answer = f'"{REAL_SAYING}" and also "{REAL_SAYING_2}"'
    quotes = extract_quotes(answer)
    assert REAL_SAYING   in quotes
    assert REAL_SAYING_2 in quotes


def test_extract_ignores_short_strings():
    # Strings shorter than 10 chars should not be extracted
    answer = '"hi" and a longer "real saying here"'
    quotes = extract_quotes(answer)
    assert "hi" not in quotes
    assert "real saying here" in quotes


def test_extract_empty_when_no_quotes():
    assert extract_quotes("No quotes in this answer.") == []


# ---------------------------------------------------------------------------
# verify_quotes — real quotes pass
# ---------------------------------------------------------------------------

def test_real_quote_passes():
    answer = f'As Poor Richard says: "{REAL_SAYING}"'
    assert verify_quotes(answer, SAYINGS) is True


def test_multiple_real_quotes_pass():
    answer = (
        f'"{REAL_SAYING}" and furthermore "{REAL_SAYING_2}" '
        "are both counsels of Poor Richard."
    )
    assert verify_quotes(answer, SAYINGS) is True


def test_no_quotes_passes():
    """An answer without any double-quoted strings trivially passes."""
    answer = "Poor Richard advises diligence in all matters."
    assert verify_quotes(answer, SAYINGS) is True


# ---------------------------------------------------------------------------
# verify_quotes — fabricated quotes fail
# ---------------------------------------------------------------------------

def test_fabricated_quote_fails():
    """A stitch in time saves nine is NOT a Franklin saying."""
    answer = 'As the proverb goes: "A stitch in time saves nine"'
    assert verify_quotes(answer, SAYINGS) is False


def test_paraphrased_quote_fails():
    """A close paraphrase that isn't verbatim must fail."""
    paraphrase = "Early to rise and early to bed makes a man healthy, wealthy, and wise"
    answer = f'Poor Richard says: "{paraphrase}"'
    assert verify_quotes(answer, SAYINGS) is False


def test_partial_but_non_substring_fails():
    """Quote must be a substring of a retrieved saying, not just similar."""
    answer = f'"{REAL_SAYING[:20]} ... and wise"'
    assert verify_quotes(answer, SAYINGS) is False


# ---------------------------------------------------------------------------
# verify_quotes — empty sayings list
# ---------------------------------------------------------------------------

def test_no_sayings_no_quotes_passes():
    assert verify_quotes("A plain answer.", []) is True


def test_quote_with_empty_sayings_fails():
    answer = f'"{REAL_SAYING}"'
    assert verify_quotes(answer, []) is False
