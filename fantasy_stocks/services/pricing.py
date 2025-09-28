# fantasy_stocks/services/pricing.py
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from .periods import iso_week_bounds  # fixed: import directly

__all__ = ["get_week_return_pct", "weekly_change"]


def get_week_return_pct(db: Session, symbol: str, iso_week: str) -> float:
    """
    Compute % return for `symbol` across the given ISO week:
      ((last_close - first_open) / first_open) * 100
    """
    start_d, end_d = iso_week_bounds(iso_week)

    rows: list[models.Price] = (
        db.query(models.Price)
        .filter(
            models.Price.symbol == symbol,
            models.Price.date >= start_d,
            models.Price.date <= end_d,
        )
        .order_by(models.Price.date.asc())
        .all()
    )

    if not rows:
        return 0.0

    first = rows[0]
    last = rows[-1]

    first_open = first.open if first.open is not None else first.close
    last_close = last.close if last.close is not None else last.open

    if first_open is None or first_open == 0 or last_close is None:
        return 0.0

    return float((last_close - first_open) / first_open * 100.0)


def weekly_change(db: Session, symbol: str, iso_week: str) -> float:
    """
    Backward-compatible alias for get_week_return_pct.
    """
    return get_week_return_pct(db, symbol, iso_week)
