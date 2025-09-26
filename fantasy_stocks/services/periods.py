# fantasy_stocks/services/periods.py
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple

__all__ = [
    "iso_week_label",
    "current_week_label",
    "iso_week_bounds",
    "next_weeks",
]

# ---------------------------------------------------------------------------
# ISO week utilities
# - Labels use "YYYY-Www" (e.g., "2025-W39")
# - Bounds are Monday..Sunday inclusive, per ISO-8601
# ---------------------------------------------------------------------------

def iso_week_label(d: date) -> str:
    """
    Return ISO week label 'YYYY-Www' for a given date.
    """
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def current_week_label(today: date | None = None) -> str:
    """
    Current ISO week label, optionally for a provided 'today' date.
    """
    if today is None:
        today = date.today()
    return iso_week_label(today)


def _parse_iso_week(iso_week: str) -> tuple[int, int]:
    """
    Parse 'YYYY-Www' -> (year, week).
    """
    try:
        year_str, week_str = iso_week.split("-W")
        return int(year_str), int(week_str)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid iso_week '{iso_week}'. Expected 'YYYY-Www'.") from exc


def iso_week_bounds(iso_week: str) -> Tuple[date, date]:
    """
    Given an ISO week label 'YYYY-Www', return (monday, sunday) dates inclusive.
    """
    year, week = _parse_iso_week(iso_week)
    monday = date.fromisocalendar(year, week, 1)  # Monday
    sunday = monday + timedelta(days=6)
    return monday, sunday


def next_weeks(start_iso_week: str, n: int) -> List[str]:
    """
    Return the next n ISO week labels starting *after* start_iso_week.
    Example: next_weeks("2025-W39", 2) -> ["2025-W40", "2025-W41"]
    """
    year, week = _parse_iso_week(start_iso_week)
    # Start from the Monday of the *next* week
    start_monday = date.fromisocalendar(year, week, 1) + timedelta(days=7)

    labels: List[str] = []
    cur = start_monday
    for _ in range(n):
        labels.append(iso_week_label(cur))
        cur = cur + timedelta(days=7)
    return labels
