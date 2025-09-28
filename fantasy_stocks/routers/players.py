# fantasy_stocks/routers/players.py
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/players", tags=["players"])

# ---------- Schemas ----------


class SecurityIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    name: str | None = None
    is_etf: bool | None = None
    market_cap: float | None = None
    sector: str | None = None
    primary_bucket: str | None = None
    adp: float | None = None
    proj_points: float | None = None


class SecurityOut(BaseModel):
    symbol: str
    name: str | None = None
    is_etf: bool | None = None
    market_cap: float | None = None
    sector: str | None = None
    primary_bucket: str | None = None
    adp: float | None = None
    proj_points: float | None = None


class IngestCSVBody(BaseModel):
    """
    CSV text with header. Columns supported (case-insensitive):
      symbol (required), name, is_etf, market_cap, sector, primary_bucket, adp, proj_points
    """

    csv: str = Field(..., description="Raw CSV text including header row")
    upsert: bool = Field(True, description="Upsert rows by symbol (insert or update existing)")


# ---------- Helpers ----------


def _to_bool(v: str | None) -> bool | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "t", "1", "yes", "y"):
        return True
    if s in ("false", "f", "0", "no", "n"):
        return False
    return None


def _to_float(v: str | None) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ---------- Endpoints ----------


@router.post("/seed")
def seed_securities(items: list[SecurityIn], db: Session = Depends(get_db)):
    """
    Upsert a list of securities for dev/test.
    """
    upserted = []
    for it in items:
        sym = it.symbol.strip().upper()
        row = db.get(models.Security, sym)
        if not row:
            row = models.Security(symbol=sym)
            db.add(row)
        row.name = it.name
        row.is_etf = it.is_etf
        row.market_cap = it.market_cap
        row.sector = it.sector
        row.primary_bucket = it.primary_bucket.strip().upper() if it.primary_bucket else None
        row.adp = it.adp
        row.proj_points = it.proj_points
        upserted.append(sym)
    db.commit()
    return {"ok": True, "upserted": upserted}


@router.post("/ingest_csv")
def ingest_csv(body: IngestCSVBody, db: Session = Depends(get_db)):
    """
    Bulk upsert securities from CSV text.
    """
    buf = io.StringIO(body.csv)
    reader = csv.DictReader(buf)

    required = {"symbol"}
    header = {h.strip().lower() for h in reader.fieldnames or []}
    if not required.issubset(header):
        return {
            "ok": False,
            "error": "missing_required_columns",
            "required": sorted(list(required)),
            "got": sorted(list(header)),
        }

    upserted: list[str] = []
    skipped: list[dict] = []
    for row in reader:
        norm = {(k or "").strip().lower(): (v if v is not None else None) for k, v in row.items()}

        sym_raw = norm.get("symbol")
        if not sym_raw or not str(sym_raw).strip():
            skipped.append({"reason": "missing_symbol", "row": row})
            continue

        sym = str(sym_raw).strip().upper()
        name = norm.get("name")
        is_etf = _to_bool(norm.get("is_etf"))
        market_cap = _to_float(norm.get("market_cap"))
        sector = norm.get("sector")
        primary_bucket = norm.get("primary_bucket") or None
        if primary_bucket:
            primary_bucket = primary_bucket.strip().upper()
        adp = _to_float(norm.get("adp"))
        proj_points = _to_float(norm.get("proj_points"))

        rec = db.get(models.Security, sym)
        if rec:
            if not body.upsert:
                skipped.append({"reason": "exists_and_upsert_false", "symbol": sym})
                continue
        else:
            rec = models.Security(symbol=sym)
            db.add(rec)

        rec.name = name
        rec.is_etf = is_etf
        rec.market_cap = market_cap
        rec.sector = sector
        rec.primary_bucket = primary_bucket
        rec.adp = adp
        rec.proj_points = proj_points

        upserted.append(sym)

    db.commit()
    return {"ok": True, "upserted": upserted, "skipped": skipped}


@router.post("/reset")
def reset_players_table(db: Session = Depends(get_db)):
    """
    TEST-ONLY helper: wipe the securities catalog.
    Safe in test DB since we recreate schema each run.
    """
    db.query(models.Security).delete()
    db.commit()
    return {"ok": True, "deleted": True}


@router.get("/search", response_model=list[SecurityOut])
def search_players(
    q: str | None = Query(None, description="Search by name or symbol"),
    bucket: str | None = Query(None, description="Filter by primary bucket"),
    is_etf: bool | None = Query(None),
    min_cap: float | None = Query(None, description="Minimum market cap (inclusive)"),
    max_cap: float | None = Query(None, description="Maximum market cap (inclusive)"),
    sector: str | None = Query(None),
    available_in_league: int | None = Query(
        None, description="League ID to exclude rostered symbols"
    ),
    # NEW sorting
    sort: str | None = Query(None, description="symbol|market_cap|adp|proj_points"),
    order: str | None = Query(None, description="asc|desc"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Search the securities catalog with filters. If available_in_league is provided,
    exclude symbols currently rostered by any team in that league.
    """
    query = db.query(models.Security)

    if q:
        qq = f"%{q.strip()}%"
        query = query.filter(or_(models.Security.symbol.ilike(qq), models.Security.name.ilike(qq)))

    if bucket:
        query = query.filter(models.Security.primary_bucket == bucket.strip().upper())

    if is_etf is not None:
        query = query.filter(models.Security.is_etf == bool(is_etf))

    if min_cap is not None:
        query = query.filter(models.Security.market_cap >= float(min_cap))

    if max_cap is not None:
        query = query.filter(models.Security.market_cap <= float(max_cap))

    if sector:
        query = query.filter(models.Security.sector == sector.strip())

    if available_in_league:
        rostered_symbols_sq = (
            select(models.RosterSlot.symbol)
            .join(models.Team, models.Team.id == models.RosterSlot.team_id)
            .where(models.Team.league_id == available_in_league)
            .scalar_subquery()
        )
        query = query.filter(~models.Security.symbol.in_(rostered_symbols_sq))

    # Sorting
    sort_map = {
        "symbol": models.Security.symbol.asc(),
        "market_cap": models.Security.market_cap.desc(),  # default: larger first
        "adp": models.Security.adp.asc(),  # default: lower first
        "proj_points": models.Security.proj_points.desc(),  # default: higher first
    }
    if sort:
        key = sort.strip().lower()
        clause = sort_map.get(key)
        if clause is not None:
            # Apply order override if provided
            if order and order.strip().lower() == "asc":
                if key in ("market_cap", "proj_points"):
                    clause = clause.reverse()  # make asc
            elif order and order.strip().lower() == "desc":
                if key in ("symbol", "adp"):
                    clause = clause.reverse()  # make desc
            query = query.order_by(clause, models.Security.symbol.asc())
        else:
            query = query.order_by(models.Security.symbol.asc())
    else:
        query = query.order_by(models.Security.symbol.asc())

    rows = query.limit(limit).all()

    return [
        SecurityOut(
            symbol=r.symbol,
            name=r.name,
            is_etf=r.is_etf,
            market_cap=r.market_cap,
            sector=r.sector,
            primary_bucket=r.primary_bucket,
            adp=r.adp,
            proj_points=r.proj_points,
        )
        for r in rows
    ]
