# fantasy_stocks/logic/auto_placement.py
from __future__ import annotations
from typing import Dict, Tuple
from sqlalchemy.orm import Session

from .. import models
from .lineup_rules import (
    BUCKET_LARGE_CAP,
    BUCKET_MID_CAP,
    BUCKET_SMALL_CAP,
    BUCKET_ETF,
    PRIMARY,
    REQUIRED,   # includes FLEX: 2
)

PRIMARY_REQUIRED: Dict[str, int] = {
    BUCKET_LARGE_CAP: REQUIRED[BUCKET_LARGE_CAP],
    BUCKET_MID_CAP:   REQUIRED[BUCKET_MID_CAP],
    BUCKET_SMALL_CAP: REQUIRED[BUCKET_SMALL_CAP],
    BUCKET_ETF:       REQUIRED[BUCKET_ETF],
}
FLEX_CAP = REQUIRED["FLEX"]
STARTERS_TOTAL = sum(PRIMARY_REQUIRED.values()) + FLEX_CAP  # 8


def _count_primary(db: Session, team_id: int) -> Tuple[Dict[str, int], int]:
    """Return counts of ACTIVE starters by primary bucket and total active."""
    rows = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team_id, models.RosterSlot.is_active == True)
        .all()
    )
    counts: Dict[str, int] = {}
    total = 0
    for s in rows:
        b = (s.bucket or "").upper()
        if b in PRIMARY:
            counts[b] = counts.get(b, 0) + 1
            total += 1
        elif b == "FLEX":
            # Treat literal FLEX as a placeholder; count as +1 to total
            # It will be allocated later; here we just include in active total
            total += 1
        else:
            # unknown buckets don't count toward primaries
            pass
    return counts, total


def _surplus(counts: Dict[str, int]) -> int:
    return sum(max(0, counts.get(b, 0) - PRIMARY_REQUIRED[b]) for b in PRIMARY)


def _remaining_primary_deficit(counts: Dict[str, int]) -> int:
    return sum(max(0, PRIMARY_REQUIRED[b] - counts.get(b, 0)) for b in PRIMARY)


def _can_activate_now(counts: Dict[str, int], total_active: int, new_bucket: str) -> bool:
    """Decide if we should set is_active=True for the new slot."""
    if total_active >= STARTERS_TOTAL:
        return False

    new_bucket = new_bucket.upper()
    # Current snapshot
    curr_surplus = _surplus(counts)

    # Case 1: still missing this primary bucket -> activate
    if counts.get(new_bucket, 0) < PRIMARY_REQUIRED[new_bucket]:
        after_counts = counts.copy()
        after_counts[new_bucket] = after_counts.get(new_bucket, 0) + 1
        after_total = total_active + 1

        # Ensure we don't paint ourselves into a corner:
        remaining_slots = STARTERS_TOTAL - after_total
        remaining_deficit = _remaining_primary_deficit(after_counts)
        return remaining_slots >= remaining_deficit

    # Case 2: primary is full; try to use FLEX capacity
    # Surplus after adding this would be curr_surplus + 1
    if curr_surplus + 1 <= FLEX_CAP:
        after_counts = counts.copy()
        after_counts[new_bucket] = after_counts.get(new_bucket, 0) + 1
        after_total = total_active + 1

        remaining_slots = STARTERS_TOTAL - after_total
        remaining_deficit = _remaining_primary_deficit(after_counts)
        return remaining_slots >= remaining_deficit

    # Otherwise, bench
    return False


def auto_place_new_slot(db: Session, team_id: int, slot_id: int, primary_bucket: str) -> dict:
    """
    Decide activation for a newly acquired roster slot.
    - Ensures slot has bucket set to the provided primary_bucket
    - Sets is_active based on primary-first -> flex -> bench rules
    Returns dict with placement info.
    """
    slot = db.get(models.RosterSlot, slot_id)
    if not slot or slot.team_id != team_id:
        return {"ok": False, "error": "slot_not_found_or_wrong_team"}

    # Normalize bucket
    b = (primary_bucket or "").upper()
    if b not in (set(PRIMARY) | {"FLEX"}):
        return {"ok": False, "error": f"invalid_bucket:{primary_bucket}"}

    # Force slot.bucket to the PRIMARY bucket (never store FLEX on new additions)
    if slot.bucket != b:
        slot.bucket = b

    counts, total_active = _count_primary(db, team_id)
    # Decide activation
    activate = _can_activate_now(counts, total_active, b)

    # Persist
    changed = False
    if slot.is_active != activate:
        slot.is_active = activate
        changed = True
    if changed:
        db.commit()
        db.refresh(slot)

    return {
        "ok": True,
        "activated": bool(activate),
        "team_id": team_id,
        "slot_id": slot.id,
        "bucket": slot.bucket,
    }
