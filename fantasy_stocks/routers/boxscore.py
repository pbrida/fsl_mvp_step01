# fantasy_stocks/routers/boxscore.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/boxscore", tags=["boxscore"])

# Keep these in sync with your fixed rules used elsewhere:
PRIMARY_REQUIREMENTS: dict[str, int] = {
    "LARGE_CAP": 2,
    "MID_CAP": 1,
    "SMALL_CAP": 2,
    "ETF": 1,
}
FLEX_SLOTS = 2
STARTERS_TOTAL = sum(PRIMARY_REQUIREMENTS.values()) + FLEX_SLOTS  # 8


def _active_slots_with_points(db: Session, team_id: int) -> list[dict]:
    """
    Return active roster slots for a team joined with Security to grab proj_points.
    """
    rows = (
        db.query(models.RosterSlot, models.Security.proj_points)
        .outerjoin(models.Security, models.Security.symbol == models.RosterSlot.symbol)
        .filter(models.RosterSlot.team_id == team_id, models.RosterSlot.is_active == True)  # noqa: E712
        .order_by(models.RosterSlot.id.asc())
        .all()
    )
    out: list[dict] = []
    for rs, proj in rows:
        out.append(
            {
                "slot_id": rs.id,
                "symbol": rs.symbol,
                "bucket": (rs.bucket or "").strip().upper() or None,
                "points": float(proj or 0.0),
            }
        )
    return out


@router.get("/{league_id}/{week}/{team_id}")
def team_boxscore(
    league_id: int = Path(..., ge=1),
    week: str = Path(..., description="ISO week label, e.g., 2025-W39"),
    team_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    Produce a per-team weekly box score using current ACTIVE starters:
      - Which starters counted toward PRIMARY buckets
      - Which surplus counted as FLEX (max 2)
      - Which active starters didn't count (shouldn't happen under current rules, but listed for transparency)
      - Per-slot points from `proj_points` (live data later)
      - Totals for primary and flex, plus grand total

    Note: This endpoint is independent of whether the week is closed. It reflects
    the *current* active lineup and bucket assignment for the given team.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    team = db.get(models.Team, team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=404, detail="Team not found in this league")

    # Confirm the week exists in schedule (optional sanity check)
    has_week = db.query(models.Match.id).filter(models.Match.league_id == league_id, models.Match.week == week).first()
    if not has_week:
        # We allow returning a box score even if the schedule hasn't included this week yet,
        # but it's helpful to alert the caller.
        pass

    # Gather active starters with their buckets/points
    active = _active_slots_with_points(db, team_id=team.id)

    # Group by bucket for allocation
    by_bucket: dict[str, list[dict]] = {}
    for s in active:
        b = s["bucket"]
        if not b:
            # No bucket → cannot count toward primary or flex; expose in "unused"
            by_bucket.setdefault("_NONE_", []).append(s)
            continue
        by_bucket.setdefault(b, []).append(s)

    # PRIMARY allocation
    primary_used: dict[str, list[dict]] = {k: [] for k in PRIMARY_REQUIREMENTS.keys()}
    primary_total_points = 0.0

    for bucket, need in PRIMARY_REQUIREMENTS.items():
        candidates = by_bucket.get(bucket, [])
        # Choose the best 'need' slots by points to be explicit
        candidates_sorted = sorted(candidates, key=lambda x: (-x["points"], x["slot_id"]))
        chosen = candidates_sorted[:need]
        for c in chosen:
            c["counted_as"] = "PRIMARY"
        primary_used[bucket] = chosen
        primary_total_points += sum(c["points"] for c in chosen)

        # Mark chosen so we don't double-count them as FLEX
        chosen_ids = {c["slot_id"] for c in chosen}
        by_bucket[bucket] = [c for c in candidates if c["slot_id"] not in chosen_ids]

    # FLEX allocation from remaining primaries
    flex_candidates: list[dict] = []
    for bucket in PRIMARY_REQUIREMENTS.keys():
        flex_candidates.extend(by_bucket.get(bucket, []))
    # Order by points high→low then by slot_id to be deterministic
    flex_candidates_sorted = sorted(flex_candidates, key=lambda x: (-x["points"], x["slot_id"]))
    flex_used = flex_candidates_sorted[:FLEX_SLOTS]
    for f in flex_used:
        f["counted_as"] = "FLEX"
    flex_total_points = sum(f["points"] for f in flex_used)

    # Unused active starters (should be uncommon)
    used_ids = {c["slot_id"] for lst in primary_used.values() for c in lst} | {f["slot_id"] for f in flex_used}
    unused_active = [s for s in active if s["slot_id"] not in used_ids]

    return {
        "league_id": league_id,
        "team_id": team.id,
        "team_name": team.name,
        "week": week,
        "requirements": {
            "primary": PRIMARY_REQUIREMENTS,
            "flex": FLEX_SLOTS,
            "starters_total": STARTERS_TOTAL,
        },
        "primary": {
            bucket: [
                {
                    "slot_id": x["slot_id"],
                    "symbol": x["symbol"],
                    "bucket": x["bucket"],
                    "points": x["points"],
                }
                for x in lst
            ]
            for bucket, lst in primary_used.items()
        },
        "flex": [
            {
                "slot_id": x["slot_id"],
                "symbol": x["symbol"],
                "bucket": x["bucket"],
                "points": x["points"],
            }
            for x in flex_used
        ],
        "unused_active": [
            {
                "slot_id": x["slot_id"],
                "symbol": x["symbol"],
                "bucket": x["bucket"],
                "points": x["points"],
            }
            for x in unused_active
        ],
        "totals": {
            "primary_points": round(primary_total_points, 4),
            "flex_points": round(flex_total_points, 4),
            "grand_total": round(primary_total_points + flex_total_points, 4),
        },
    }
