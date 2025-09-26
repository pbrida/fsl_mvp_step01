# fantasy_stocks/routers/lineup.py
from __future__ import annotations

from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..logic.lineup_rules import (
    validate_starter_buckets,
    BUCKET_LARGE_CAP,
    BUCKET_MID_CAP,
    BUCKET_SMALL_CAP,
    BUCKET_ETF,
    FLEX,
    PRIMARY,
)

router = APIRouter(prefix="/lineup", tags=["lineup"])


class SetLineupBody(BaseModel):
    team_id: int = Field(..., ge=1)
    slot_ids: List[int] = Field(..., min_length=1, description="Exactly 8 slot IDs for starters")


def _upper(s: str | None) -> str:
    return (s or "").strip().upper()


def _synthetic_primary_selection_from_slots(buckets: List[str]) -> List[str]:
    """
    Convert selected 8 buckets (some may literally be 'FLEX') into a list of 8 *primary* bucket labels.
    Strategy:
      - Count primaries directly (LARGE_CAP, MID_CAP, SMALL_CAP, ETF).
      - Treat any 'FLEX' labels as placeholders.
      - First spend placeholders to fill *primary deficits* up to required amounts.
      - Assign any remaining placeholders to primaries (these become surplus -> FLEX).
    Result length is always 8 (same as input).
    """
    # Count primaries; collect flex placeholders
    primaries: List[str] = []
    flex_placeholders = 0
    for b in buckets:
        bu = _upper(b)
        if bu in PRIMARY:
            primaries.append(bu)
        elif bu == FLEX:
            flex_placeholders += 1
        else:
            # Unknown/empty bucket; keep as-is so validator errors clearly
            primaries.append(bu)

    # Compute current counts
    def _count(ls: List[str]) -> Dict[str, int]:
        d: Dict[str, int] = {}
        for x in ls:
            d[x] = d.get(x, 0) + 1
        return d

    counts = _count(primaries)

    # Primary requirements
    required_primary = {
        BUCKET_LARGE_CAP: 2,
        BUCKET_MID_CAP: 1,
        BUCKET_SMALL_CAP: 2,
        BUCKET_ETF: 1,
    }

    # Fill deficits with placeholders
    for label in [BUCKET_LARGE_CAP, BUCKET_MID_CAP, BUCKET_SMALL_CAP, BUCKET_ETF]:
        need = required_primary[label]
        have = counts.get(label, 0)
        missing = max(0, need - have)
        use = min(missing, flex_placeholders)
        if use > 0:
            primaries.extend([label] * use)
            counts[label] = have + use
            flex_placeholders -= use
        if flex_placeholders == 0:
            break

    # Any remaining placeholders become surplus (to satisfy FLEX)
    if flex_placeholders > 0:
        roll = [BUCKET_LARGE_CAP, BUCKET_MID_CAP, BUCKET_SMALL_CAP, BUCKET_ETF]
        i = 0
        while flex_placeholders > 0:
            primaries.append(roll[i % len(roll)])
            i += 1
            flex_placeholders -= 1

    return primaries[: len(buckets)]


@router.post("/set")
def set_lineup(body: SetLineupBody, db: Session = Depends(get_db)):
    """
    Activates exactly 8 roster slots for the given team using true FLEX logic.

    Inputs:
      - team_id
      - slot_ids: 8 slot IDs from this team

    Behavior:
      - Validates team/slot ownership and count == 8
      - Builds an 8-length list of primary buckets (ignores literal 'FLEX' labels as placeholders)
      - Validates distribution via validate_starter_buckets() (FLEX auto-satisfied by surplus)
      - Marks those 8 slots as active; all other team slots become bench (inactive)
    """
    # --- Validate team exists
    team = db.get(models.Team, body.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # --- Load selected slots and ownership
    if len(body.slot_ids) != 8:
        raise HTTPException(status_code=400, detail="Exactly 8 slot_ids are required")

    slots = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.id.in_(body.slot_ids))
        .all()
    )
    if len(slots) != len(body.slot_ids):
        raise HTTPException(status_code=400, detail="One or more slot_ids do not exist")

    # Ensure all belong to the same team
    bad = [s.id for s in slots if s.team_id != team.id]
    if bad:
        raise HTTPException(
            status_code=400,
            detail={"ownership_error": f"Slots not owned by team {team.id}", "slot_ids": bad},
        )

    # --- Build bucket list from slot.bucket (string)
    selected_buckets_raw = [_upper(s.bucket) for s in slots]
    # If any bucket is empty/unknown, bail early with a friendly error
    if any(not b or b not in (set(PRIMARY) | {FLEX}) for b in selected_buckets_raw):
        raise HTTPException(
            status_code=400,
            detail={
                "invalid_bucket": True,
                "expected": list(PRIMARY) + [FLEX],
                "got": selected_buckets_raw,
                "hint": "Ensure each selected slot has a valid bucket assigned.",
            },
        )

    synthetic = _synthetic_primary_selection_from_slots(selected_buckets_raw)

    # --- Validate against fixed rules (FLEX derived from surplus)
    ok, detail = validate_starter_buckets(synthetic)
    if not ok:
        raise HTTPException(status_code=400, detail=detail)

    # --- Persist: mark exactly these slots as active (bench all others)
    team_all_slots = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id)
        .all()
    )
    selected_set = set(body.slot_ids)
    changed = False
    for s in team_all_slots:
        new_active = s.id in selected_set
        if getattr(s, "is_active", False) != new_active:
            setattr(s, "is_active", new_active)
            changed = True

    if changed:
        db.commit()

    return {
        "ok": True,
        "team_id": team.id,
        "starters": sorted(list(selected_set)),
        "validation": detail,
    }
