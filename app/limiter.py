"""
Rate limiting (per-IP via slowapi) and daily API spend cap (in-memory).
"""

from __future__ import annotations

import os
import threading
from datetime import date, datetime, timezone

from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_STRING = os.getenv("RATE_LIMIT_ASK", "5/minute")
DAILY_SPEND_CAP   = float(os.getenv("DAILY_SPEND_CAP_USD", "1.0"))

# Estimated cost per /ask call in USD (conservative upper bound)
# claude-haiku-4-5: ~500 input tokens + ~300 output tokens
# Input $0.80/MTok, Output $4.00/MTok  → ~$0.00160/call
ESTIMATED_COST_PER_CALL = float(os.getenv("ESTIMATED_COST_PER_CALL", "0.002"))

limiter = Limiter(key_func=get_remote_address)

# Thread-safe daily spend tracker
_lock        = threading.Lock()
_spend_date  = date.today()
_daily_spend = 0.0


def check_and_charge() -> bool:
    """
    Returns True if the call is allowed (and charges the estimated cost).
    Returns False if the daily cap would be exceeded.
    """
    global _spend_date, _daily_spend
    today = datetime.now(timezone.utc).date()
    with _lock:
        if today != _spend_date:
            _spend_date  = today
            _daily_spend = 0.0
        if _daily_spend + ESTIMATED_COST_PER_CALL > DAILY_SPEND_CAP:
            return False
        _daily_spend += ESTIMATED_COST_PER_CALL
    return True


def current_spend() -> float:
    """Return today's accumulated spend (for health/metrics)."""
    with _lock:
        return _daily_spend
