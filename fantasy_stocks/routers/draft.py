# fantasy_stocks/routers/draft.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..logic.auto_placement import auto_place_new_slot
from ..logic.ticker_registry import resolve_bucket_db_first

router = APIRouter(prefix="/draft", tags=["draft"])


class PickBody(BaseModel):
    team_id: int = Field(..., ge=1)
    symbol: str = Field(..., min_length=1, max_length=20)


class RosterSlotOut(BaseModel):
    id: int
    team_id: int
    symbol: str
    is_active: bool
    bucket: str | None = None

    @classmethod
    def from_model(cls, rs: models.RosterSlot) -> RosterSlotOut:
        return cls(
            id=rs.id,
            team_id=rs.team_id,
            symbol=rs.symbol,
            is_active=bool(getattr(rs, "is_active", False)),
            bucket=rs.bucket,
        )


class SetBucketBody(BaseModel):
    bucket: str = Field(..., min_length=1, max_length=32)


def _upper(s: str | None) -> str:
    return (s or "").strip().upper()


def _next_pick_no_for_league(db: Session, league_id: int) -> int:
    count = db.query(models.DraftPick).filter(models.DraftPick.league_id == league_id).count()
    return count + 1


@router.post("/pick")
def make_pick(body: PickBody, db: Session = Depends(get_db)):
    team = db.get(models.Team, body.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    symbol = body.symbol.strip().upper()
    league_id = team.league_id
    pick_no = _next_pick_no_for_league(db, league_id)

    dp = models.DraftPick(
        league_id=league_id,
        team_id=team.id,
        symbol=symbol,
        round=1,
        pick_no=pick_no,
    )
    db.add(dp)

    # DB-first resolution (securities), fallback to in-memory
    resolved = resolve_bucket_db_first(db, symbol)

    slot = models.RosterSlot(
        team_id=team.id,
        symbol=symbol,
        bucket=resolved,
        is_active=False,
    )
    db.add(slot)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="This team already drafted that symbol.")

    db.refresh(dp)
    db.refresh(slot)

    placement = None
    if resolved:
        placement = auto_place_new_slot(
            db, team_id=team.id, slot_id=slot.id, primary_bucket=resolved
        )

    return {
        "ok": True,
        "draft_pick": {
            "id": dp.id,
            "league_id": dp.league_id,
            "team_id": dp.team_id,
            "symbol": dp.symbol,
            "round": dp.round,
            "pick_no": dp.pick_no,
        },
        "slot": RosterSlotOut.from_model(slot).model_dump(),
        "bucket_resolved": bool(resolved),
        "placement": placement,
        "hint": (
            None if resolved else "No registry/DB mapping; slot left inactive until bucket is set."
        ),
    }


@router.get("/roster/{team_id}", response_model=list[RosterSlotOut])
def roster(team_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    rows = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id)
        .order_by(models.RosterSlot.id.asc())
        .all()
    )
    return [RosterSlotOut.from_model(r) for r in rows]


@router.patch("/slot/{slot_id}/bucket", response_model=RosterSlotOut)
def set_slot_bucket(slot_id: int, body: SetBucketBody, db: Session = Depends(get_db)):
    slot = db.get(models.RosterSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Roster slot not found")

    new_bucket = _upper(body.bucket)
    if not new_bucket:
        raise HTTPException(status_code=400, detail="bucket cannot be empty")

    changed = False
    if slot.bucket != new_bucket:
        slot.bucket = new_bucket
        changed = True

    if changed:
        db.commit()
        db.refresh(slot)

    return RosterSlotOut.from_model(slot)
