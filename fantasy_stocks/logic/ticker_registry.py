# fantasy_stocks/logic/ticker_registry.py
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session

from .. import models

# MVP in-memory registry (fallback). Keep minimal—tests/dev only.
_TICKER_TO_BUCKET = {
    # ETFs
    "VTI": "ETF",
    "VOO": "ETF",

    # Small-cap
    "SHOP": "SMALL_CAP",

    # Large caps (defaults)
    "AAPL": "LARGE_CAP",
    "MSFT": "LARGE_CAP",
    "TSLA": "LARGE_CAP",
    "GOOGL": "LARGE_CAP",
    "AMZN": "LARGE_CAP",
    "NVDA": "LARGE_CAP",
    "META": "LARGE_CAP",
    "ADBE": "LARGE_CAP",
    "NFLX": "LARGE_CAP",
    "PG": "LARGE_CAP",
    "KO": "SMALL_CAP",
    "SHEL": "LARGE_CAP",
    "BABA": "LARGE_CAP",
}

def resolve_bucket(symbol: str) -> Optional[str]:
    """Pure in-memory fallback resolver."""
    if not symbol:
        return None
    return _TICKER_TO_BUCKET.get(symbol.strip().upper())

# ---- DB-first resolver (preferred) ----

# Simple, tweakable thresholds (can move to config later)
_LARGE_MIN = 10_000_000_000  # >= $10B
_MID_MIN   =  2_000_000_000  # $2B–$10B is mid; < $2B is small

def _derive_bucket_from_row(row: models.Security) -> Optional[str]:
    if row is None:
        return None
    # 1) explicit ETF
    if row.is_etf is True:
        return "ETF"
    # 2) cached bucket if present
    if row.primary_bucket:
        return row.primary_bucket.strip().upper()
    # 3) derive from market cap if available
    mc = row.market_cap or 0.0
    if mc >= _LARGE_MIN:
        return "LARGE_CAP"
    if mc >= _MID_MIN:
        return "MID_CAP"
    if mc > 0:
        return "SMALL_CAP"
    return None

def resolve_bucket_db_first(db: Session, symbol: str) -> Optional[str]:
    """
    Preferred resolution path:
      1) Look up in `securities` table, return cached/derived bucket if possible.
      2) Fall back to in-memory map.
    """
    if not symbol:
        return None
    sym = symbol.strip().upper()
    row = db.get(models.Security, sym)
    b = _derive_bucket_from_row(row)
    if b:
        return b
    return _TICKER_TO_BUCKET.get(sym)
