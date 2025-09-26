# fantasy_stocks/routers/teams.py
from __future__ import annotations

from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models

router = APIRouter(prefix="/teams", tags=["teams"])

# Fixed roster requirements (as agreed):
# 2 LARGE_CAP, 1 MID_CAP, 2 SMALL_CAP, 1 ETF, 2 FLEX (total starters = 8)
PRIMARY_REQUIREMENTS: Dict[str, int] = {
    "LARGE_CAP": 2,
    "MID_CAP": 1,
    "SMALL_CAP": 2,
    "ETF": 1,
}
FLEX_SLOTS = 2
STARTERS_TOTAL = sum(PRIMARY_REQUIREMENTS.values()) + FLEX_SLOTS  # = 8


@router.get("/{team_id}/needs")
def team_needs(team_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """
    Return how many starters the team still needs to fill by bucket, plus FLEX capacity.

    Logic:
      1) Count ACTIVE roster slots by bucket.
      2) Allocate toward PRIMARY buckets first (capped by requirement).
      3) Any surplus beyond primary requirements can count toward FLEX (up to 2).
      4) Report 'need' vs 'got' for each primary bucket and FLEX.

    Notes:
      - We don't track explicit "this slot is FLEX" — we infer FLEX fill by surplus starters.
      - If an active slot has bucket=None, it is ignored (won't count toward primary or FLEX).
      - The endpoint also returns helpful summary totals.
    """
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    league = db.get(models.League, team.league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # 1) Pull active starters
    active_slots = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id, models.RosterSlot.is_active == True)  # noqa: E712
        .all()
    )

    # Count active by bucket (ignore None)
    raw_counts: Dict[str, int] = {}
    for rs in active_slots:
        b = (rs.bucket or "").strip().upper()
        if not b:
            continue
        raw_counts[b] = raw_counts.get(b, 0) + 1

    # 2) Allocate toward primary requirements
    primary_got: Dict[str, int] = {}
    for bucket, need in PRIMARY_REQUIREMENTS.items():
        got = min(raw_counts.get(bucket, 0), need)
        primary_got[bucket] = got

    # 3) Compute FLEX from surplus across allowed primary buckets
    surplus = 0
    for bucket, need in PRIMARY_REQUIREMENTS.items():
        count_b = raw_counts.get(bucket, 0)
        if count_b > need:
            surplus += (count_b - need)
    flex_got = min(surplus, FLEX_SLOTS)

    # Needs
    needs: Dict[str, Dict[str, int]] = {}
    for bucket, need in PRIMARY_REQUIREMENTS.items():
        got = primary_got[bucket]
        needs[bucket] = {"need": need, "got": got}
    needs["FLEX"] = {"need": FLEX_SLOTS, "got": flex_got}

    # Summary
    primary_total_got = sum(primary_got.values())
    inferred_starters_got = primary_total_got + flex_got
    starters_remaining = max(0, STARTERS_TOTAL - inferred_starters_got)

    summary = {
        "starters_required": STARTERS_TOTAL,
        "starters_got": inferred_starters_got,
        "starters_remaining": starters_remaining,
        "active_slots_found": len(active_slots),
    }

    return {
        "team_id": team.id,
        "league_id": league.id,
        "requirements": needs,
        "counts_active_by_bucket": raw_counts,
        "allocation_primary_got": primary_got,
        "flex_got": flex_got,
        "summary": summary,
    }
