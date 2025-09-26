# fantasy_stocks/routers/free_agency.py
from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_, select  # <- use select

from ..db import get_db
from .. import models
from ..logic.auto_placement import auto_place_new_slot
from ..logic.ticker_registry import resolve_bucket_db_first

router = APIRouter(prefix="/free-agency", tags=["free_agency"])


class FreeAgentPlayer(BaseModel):
    player_id: int
    name: str
    ticker: Optional[str] = None
    bucket: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ClaimRequest(BaseModel):
    league_id: int
    team_id: int
    player_id: int
    ticker: Optional[str] = None          # prefer real ticker if available
    primary_bucket: Optional[str] = None  # compatibility path
    bid_amount: Optional[float] = None


class DropRequest(BaseModel):
    league_id: int
    team_id: int
    symbol: str


class AddRequest(BaseModel):
    league_id: int
    team_id: int
    player_id: int
    ticker: Optional[str] = None
    primary_bucket: Optional[str] = None
    override_waivers: bool = False


@router.get("/{league_id}/players", response_model=List[FreeAgentPlayer])
def list_free_agents(
    league_id: int = Path(..., ge=1),
    q: Optional[str] = Query(None, description="Search by name/symbol"),
    bucket: Optional[str] = Query(None, description="Filter by primary bucket (e.g., ETF)"),
    sort: Optional[str] = Query(None, description="symbol|market_cap|adp|proj_points"),
    order: Optional[str] = Query(None, description="asc|desc"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rostered_symbols_sq = (
        select(models.RosterSlot.symbol)
        .join(models.Team, models.Team.id == models.RosterSlot.team_id)
        .where(models.Team.league_id == league_id)
        .scalar_subquery()
    )
    query = db.query(models.Security).filter(~models.Security.symbol.in_(rostered_symbols_sq))

    if q:
        qq = f"%{q.strip()}%"
        query = query.filter(or_(models.Security.symbol.ilike(qq), models.Security.name.ilike(qq)))
    if bucket:
        query = query.filter(models.Security.primary_bucket == bucket.strip().upper())

    sort_map = {
        "symbol": models.Security.symbol.asc(),
        "market_cap": models.Security.market_cap.desc(),
        "adp": models.Security.adp.asc(),
        "proj_points": models.Security.proj_points.desc(),
    }
    if sort:
        key = sort.strip().lower()
        clause = sort_map.get(key)
        if clause is not None:
            if order and order.strip().lower() == "asc":
                if key in ("market_cap", "proj_points"):
                    clause = clause.reverse()
            elif order and order.strip().lower() == "desc":
                if key in ("symbol", "adp"):
                    clause = clause.reverse()
            query = query.order_by(clause, models.Security.symbol.asc())
        else:
            query = query.order_by(models.Security.symbol.asc())
    else:
        query = query.order_by(models.Security.symbol.asc())

    rows = query.limit(limit).all()

    out: List[FreeAgentPlayer] = []
    pid = 1
    for r in rows:
        out.append(
            FreeAgentPlayer(
                player_id=pid,
                name=r.name or r.symbol,
                ticker=r.symbol,
                bucket=r.primary_bucket,
                meta={
                    "sector": r.sector,
                    "market_cap": r.market_cap,
                    "is_etf": r.is_etf,
                    "adp": r.adp,
                    "proj_points": r.proj_points,
                },
            )
        )
        pid += 1
    return out


@router.post("/{league_id}/claim")
def claim_player(
    league_id: int,
    body: ClaimRequest,
    db: Session = Depends(get_db),
):
    if body.league_id != league_id:
        raise HTTPException(status_code=400, detail="league_id mismatch in path vs body")

    team = db.get(models.Team, body.team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=404, detail="Team not found in this league")

    if body.ticker:
        symbol = body.ticker.strip().upper()
        resolved = resolve_bucket_db_first(db, symbol)
    else:
        symbol = f"PID{body.player_id}"
        resolved = (body.primary_bucket or "").strip().upper() or None

    slot = models.RosterSlot(team_id=team.id, symbol=symbol, bucket=resolved or None, is_active=False)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    placement = None
    if resolved:
        placement = auto_place_new_slot(db, team_id=team.id, slot_id=slot.id, primary_bucket=resolved)

    return {
        "ok": True,
        "message": "Claim processed (auto-placed if bucket resolved).",
        "placement": placement,
        "slot_id": slot.id,
        "symbol": symbol,
        "bucket_resolved": bool(resolved),
        "hint": (None if resolved else "No mapping for this ticker; slot left inactive until bucket is set."),
    }


@router.post("/{league_id}/add")
def add_player_immediate(
    league_id: int,
    body: AddRequest,
    db: Session = Depends(get_db),
):
    if body.league_id != league_id:
        raise HTTPException(status_code=400, detail="league_id mismatch in path vs body")

    team = db.get(models.Team, body.team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=404, detail="Team not found in this league")

    if body.ticker:
        symbol = body.ticker.strip().upper()
        resolved = resolve_bucket_db_first(db, symbol)
    else:
        symbol = f"PID{body.player_id}"
        resolved = (body.primary_bucket or "").strip().upper() or None

    slot = models.RosterSlot(team_id=team.id, symbol=symbol, bucket=resolved or None, is_active=False)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    placement = None
    if resolved:
        placement = auto_place_new_slot(db, team_id=team.id, slot_id=slot.id, primary_bucket=resolved)

    return {
        "ok": True,
        "message": "Player added (auto-placed if bucket resolved).",
        "placement": placement,
        "slot_id": slot.id,
        "symbol": symbol,
        "bucket_resolved": bool(resolved),
        "hint": (None if resolved else "No mapping for this ticker; slot left inactive until bucket is set."),
    }


@router.post("/{league_id}/drop")
def drop_player(
    league_id: int,
    body: DropRequest,
    db: Session = Depends(get_db),
):
    if body.league_id != league_id:
        raise HTTPException(status_code=400, detail="league_id mismatch in path vs body")

    team = db.get(models.Team, body.team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=404, detail="Team not found in this league")

    slot = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team.id, models.RosterSlot.symbol == body.symbol.strip().upper())
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Roster slot not found for that symbol")

    db.delete(slot)
    db.commit()

    return {"ok": True, "message": "Player dropped to free agency.", "symbol": body.symbol.strip().upper()}
