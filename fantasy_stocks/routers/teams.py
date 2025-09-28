from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

# NOTE: no prefix so we can define both /teams/* and /leagues/{league_id}/teams
router = APIRouter(tags=["teams"])

# ====== Fixed roster requirements (as agreed) ======
# 2 LARGE_CAP, 1 MID_CAP, 2 SMALL_CAP, 1 ETF, 2 FLEX (total starters = 8)
PRIMARY_REQUIREMENTS: dict[str, int] = {
    "LARGE_CAP": 2,
    "MID_CAP": 1,
    "SMALL_CAP": 2,
    "ETF": 1,
}
FLEX_SLOTS = 2
STARTERS_TOTAL = sum(PRIMARY_REQUIREMENTS.values()) + FLEX_SLOTS  # = 8
ALLOWED_BUCKETS = set(PRIMARY_REQUIREMENTS.keys())


def _normalize_bucket(b: Optional[str]) -> str:
    if not b:
        raise HTTPException(status_code=422, detail="bucket is required")
    b_up = b.strip().upper()
    if b_up not in ALLOWED_BUCKETS:
        raise HTTPException(
            status_code=422,
            detail=f"bucket must be one of {sorted(ALLOWED_BUCKETS)}",
        )
    return b_up


# ====== Schemas ======
class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1)


class TeamCreateFlat(BaseModel):
    league_id: int
    name: str = Field(..., min_length=1)


class TeamRead(BaseModel):
    id: int
    league_id: int
    name: str

    class Config:
        # Support both pydantic v1 & v2
        orm_mode = True
        from_attributes = True


class RosterSlotRead(BaseModel):
    id: int
    team_id: int
    symbol: str
    is_active: bool
    bucket: Optional[str]
    # Make optional to be forgiving if DB default timing differs
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True


class RosterActivateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    bucket: str = Field(..., description=f"One of: {', '.join(sorted(ALLOWED_BUCKETS))}")


class DebugSeedRequest(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    clear_existing: bool = False


# ====== League-scoped endpoints ======
@router.get("/leagues/{league_id}/teams", response_model=List[TeamRead])
def list_teams_for_league(league_id: int, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return db.query(models.Team).filter(models.Team.league_id == league_id).order_by(models.Team.id.asc()).all()


@router.post(
    "/leagues/{league_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
)
def create_team_for_league(league_id: int, body: TeamCreate, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    existing = db.query(models.Team).filter(models.Team.league_id == league_id, models.Team.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Team name already exists in this league")

    team = models.Team(league_id=league_id, name=body.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


# ====== Flat endpoints (useful for scripts/automation) ======
@router.get("/teams", response_model=List[TeamRead])
def list_teams(league_id: Optional[int] = Query(default=None), db: Session = Depends(get_db)):
    q = db.query(models.Team)
    if league_id is not None:
        q = q.filter(models.Team.league_id == league_id)
    return q.order_by(models.Team.id.asc()).all()


@router.post("/teams/", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamCreateFlat, db: Session = Depends(get_db)):
    league = db.get(models.League, body.league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    existing = (
        db.query(models.Team).filter(models.Team.league_id == body.league_id, models.Team.name == body.name).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Team name already exists in this league")

    team = models.Team(league_id=body.league_id, name=body.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


# ====== Active roster slot CRUD (simple) ======
@router.get("/teams/{team_id}/roster/active", response_model=List[RosterSlotRead])
def list_active_roster(team_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    rows = (
        db.query(models.RosterSlot)
        .filter(
            models.RosterSlot.team_id == team.id,
            models.RosterSlot.is_active == True,  # noqa: E712
        )
        .order_by(models.RosterSlot.created_at.asc())
        .all()
    )
    return rows


# Raw version to bypass the response_model (good for debugging serialization)
@router.get("/teams/{team_id}/roster/active/raw")
def list_active_roster_raw(team_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    rows = (
        db.query(models.RosterSlot)
        .filter(
            models.RosterSlot.team_id == team.id,
            models.RosterSlot.is_active == True,  # noqa: E712
        )
        .order_by(models.RosterSlot.created_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "team_id": r.team_id,
            "symbol": r.symbol,
            "bucket": r.bucket,
            "is_active": bool(r.is_active),
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        }
        for r in rows
    ]


@router.post("/teams/{team_id}/roster/active", response_model=RosterSlotRead, status_code=201)
def upsert_active_slot(team_id: int, body: RosterActivateRequest, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    bucket = _normalize_bucket(body.bucket)
    symbol = body.symbol.strip().upper()

    existing = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id, models.RosterSlot.symbol == symbol)
        .first()
    )

    if existing:
        existing.is_active = True
        existing.bucket = bucket
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    row = models.RosterSlot(
        team_id=team.id,
        symbol=symbol,
        is_active=True,
        bucket=bucket,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/teams/{team_id}/roster/active/{symbol}", status_code=204)
def remove_active_slot(team_id: int, symbol: str, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    sym = symbol.strip().upper()
    row = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id, models.RosterSlot.symbol == sym)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Active slot (symbol) not found")
    db.delete(row)
    db.commit()
    return


@router.delete("/teams/{team_id}/roster/active", status_code=200)
def clear_active_slots(team_id: int, bucket: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    q = db.query(models.RosterSlot).filter(
        models.RosterSlot.team_id == team.id,
        models.RosterSlot.is_active == True,  # noqa: E712
    )

    if bucket is not None:
        b = _normalize_bucket(bucket)
        q = q.filter(models.RosterSlot.bucket == b)

    removed = q.delete(synchronize_session=False)
    db.commit()
    return {"removed": removed, "bucket": bucket}


# ====== Your existing "needs" endpoint ======
@router.get("/teams/{team_id}/needs")
def team_needs(team_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """
    Return how many starters the team still needs to fill by bucket, plus FLEX capacity.
    """
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    league = db.get(models.League, team.league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Pull active starters
    active_slots = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id, models.RosterSlot.is_active == True)  # noqa: E712
        .all()
    )

    # Count active by bucket (ignore None)
    raw_counts: dict[str, int] = {}
    for rs in active_slots:
        b = (rs.bucket or "").strip().upper()
        if not b:
            continue
        raw_counts[b] = raw_counts.get(b, 0) + 1

    # Allocate toward primary requirements
    primary_got: dict[str, int] = {}
    for bucket, need in PRIMARY_REQUIREMENTS.items():
        got = min(raw_counts.get(bucket, 0), need)
        primary_got[bucket] = got

    # FLEX from surplus across primary buckets
    surplus = 0
    for bucket, need in PRIMARY_REQUIREMENTS.items():
        count_b = raw_counts.get(bucket, 0)
        if count_b > need:
            surplus += count_b - need
    flex_got = min(surplus, FLEX_SLOTS)

    # Needs + summary
    needs: dict[str, dict[str, int]] = {}
    for bucket, need in PRIMARY_REQUIREMENTS.items():
        got = primary_got[bucket]
        needs[bucket] = {"need": need, "got": got}
    needs["FLEX"] = {"need": FLEX_SLOTS, "got": flex_got}

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


# ====== Debug: seed N active slots per bucket (handy for testing) ======
@router.post("/teams/{team_id}/debug/seed-active")
def debug_seed_active(team_id: int, body: DebugSeedRequest, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if body.clear_existing:
        db.query(models.RosterSlot).filter(
            models.RosterSlot.team_id == team.id,
            models.RosterSlot.is_active == True,  # noqa: E712
        ).delete(synchronize_session=False)
        db.commit()

    for bucket, n in (body.counts or {}).items():
        b = _normalize_bucket(bucket)
        n_int = int(n or 0)
        for _ in range(max(0, n_int)):
            sym = f"DBG_{b[:3]}_{uuid.uuid4().hex[:6].upper()}"
            row = models.RosterSlot(team_id=team.id, symbol=sym, is_active=True, bucket=b)
            db.add(row)
    db.commit()

    # summarize now
    rows = (
        db.query(models.RosterSlot)
        .filter(
            models.RosterSlot.team_id == team.id,
            models.RosterSlot.is_active == True,  # noqa: E712
        )
        .all()
    )
    summary: dict[str, int] = {}
    for r in rows:
        if r.bucket:
            summary[r.bucket] = summary.get(r.bucket, 0) + 1

    return {"team_id": team.id, "active_summary_now": summary}
