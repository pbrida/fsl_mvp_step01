# fantasy_stocks/services/time_rules.py
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _get_et_zone() -> ZoneInfo:
    """
    Return an Eastern Time zoneinfo. Tries common keys and gives a helpful
    error if tzdata isn't installed.
    """
    for key in ("America/New_York", "US/Eastern", "EST5EDT"):
        try:
            return ZoneInfo(key)
        except ZoneInfoNotFoundError:
            continue
    # If we get here, tzdata likely isn't installed or available.
    raise RuntimeError(
        "No IANA timezone data found for Eastern Time. "
        "Install tzdata inside your venv: pip install tzdata"
    )


MARKET_TZ = _get_et_zone()

# U.S. market hours in Eastern Time
OPEN_ET = time(9, 30)  # 9:30 AM
CLOSE_ET = time(16, 0)  # 4:00 PM


def _now_et() -> datetime:
    return datetime.now(MARKET_TZ)


def is_trading_day(dt: datetime | None = None) -> bool:
    dt = dt or _now_et()
    # Monday=0 ... Sunday=6
    return dt.weekday() < 5


def is_lineup_locked(dt: datetime | None = None) -> bool:
    """
    Lock window: trading days from 9:30 AM to 4:00 PM ET.
    (Holiday handling can be added later.)
    """
    dt = dt or _now_et()
    if not is_trading_day(dt):
        return False
    t = dt.time()
    return OPEN_ET <= t <= CLOSE_ET
