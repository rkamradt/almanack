"""
Unit tests for the similarity threshold filter (app/retrieve.py).
"""

from app.retrieve import filter_by_threshold

ABOVE = {"text": "Early to bed, and early to rise", "similarity": 0.72, "year": 1735}
NEAR  = {"text": "Lost time is never found again",   "similarity": 0.36, "year": 1748}
BELOW = {"text": "Industry pays debts",              "similarity": 0.20, "year": None}


def test_above_threshold_included():
    result = filter_by_threshold([ABOVE, BELOW], threshold=0.35)
    assert ABOVE in result
    assert BELOW not in result


def test_at_threshold_included():
    """Exact match at threshold boundary should be included (≥)."""
    result = filter_by_threshold([NEAR], threshold=0.36)
    assert NEAR in result


def test_just_below_threshold_excluded():
    just_below = {"text": "A fat kitchen makes a lean will", "similarity": 0.3499, "year": None}
    result = filter_by_threshold([just_below], threshold=0.35)
    assert just_below not in result


def test_all_below_threshold_returns_empty():
    result = filter_by_threshold([BELOW], threshold=0.35)
    assert result == []


def test_all_above_threshold_returns_all():
    sayings = [ABOVE, NEAR]
    result = filter_by_threshold(sayings, threshold=0.30)
    assert set(s["text"] for s in result) == {ABOVE["text"], NEAR["text"]}


def test_empty_input_returns_empty():
    assert filter_by_threshold([], threshold=0.35) == []


def test_zero_threshold_returns_all():
    result = filter_by_threshold([ABOVE, NEAR, BELOW], threshold=0.0)
    assert len(result) == 3
