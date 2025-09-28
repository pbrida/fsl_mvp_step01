# fantasy_stocks/routers/playoffs.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services.periods import current_week_label

# ✅ Use the same ordering as our /standings tiebreakers:
#    win_pct → head-to-head (among tied) → point diff → points for → deterministic coin
from .standings import (
    _aggregate_table_rows,
    _deterministic_coin,
    _h2h_stats_among,
)

route = APIRouter(prefix="/playoffs", tags=["playoffs"])


def _seed_order_by_tiebreakers(db: Session, league_id: int) -> list[int]:
    """
    Produce a full seeding order using the same rules as /standings/{league_id}/tiebreakers:
      1) Overall win_pct
      2) Head-to-head mini-league win_pct (among the group)
      3) Point diff
      4) Points for
      5) Deterministic coin (stable hash)
    Returns team_ids sorted descending by 'goodness' (seed #1 first).
    """
    base = _aggregate_table_rows(db, league_id)  # List[schemas.TableRow]
    if not base:
        return []

    group_ids = {r.team_id for r in base}
    h2h = _h2h_stats_among(db, league_id, group_ids)

    def key_for(row) -> tuple:
        win_pct = float(row.win_pct or 0.0)
        diff = float(row.point_diff or 0.0)
        pf = float(row.points_for or 0.0)
        hs = h2h.get(row.team_id, {"wins": 0.0, "losses": 0.0, "ties": 0.0})
        g = hs["wins"] + hs["losses"] + hs["ties"]
        h2h_win_pct = (hs["wins"] + 0.5 * hs["ties"]) / g if g > 0 else 0.0
        coin = _deterministic_coin(league_id, row.team_id)
        return (win_pct, h2h_win_pct, diff, pf, coin)

    ordered = sorted(base, key=key_for, reverse=True)
    return [r.team_id for r in ordered]


def _seed_top4(db: Session, league_id: int) -> list[int]:
    """Return team_ids of seeds [1..4] using the tiebreaker-based order."""
    order = _seed_order_by_tiebreakers(db, league_id)
    if len(order) < 4:
        raise HTTPException(status_code=400, detail="Need at least 4 teams for playoffs")
    return order[:4]


@route.post("/generate/{league_id}")
def generate_playoffs(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Create two semifinal Matches for the top-4 teams by tiebreaker order.
    Weeks are labeled with current ISO week plus a suffix to avoid collisions.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    seeds = _seed_top4(db, league_id)  # [s1, s2, s3, s4]
    s1, s2, s3, s4 = seeds
    base = current_week_label()
    week_sf = f"{base}-PO-SF"

    # Prevent duplicates if already created
    existing = db.query(models.Match).filter(models.Match.league_id == league_id, models.Match.week == week_sf).count()
    if existing >= 2:
        semis = db.query(models.Match).filter(models.Match.league_id == league_id, models.Match.week == week_sf).all()
        return {
            "week": week_sf,
            "semifinals": [{"id": m.id, "home_team_id": m.home_team_id, "away_team_id": m.away_team_id} for m in semis],
        }

    m1 = models.Match(league_id=league_id, week=week_sf, home_team_id=s1, away_team_id=s4)
    m2 = models.Match(league_id=league_id, week=week_sf, home_team_id=s2, away_team_id=s3)
    db.add_all([m1, m2])
    db.commit()
    db.refresh(m1)
    db.refresh(m2)

    return {
        "week": week_sf,
        "semifinals": [
            {"id": m1.id, "home_team_id": m1.home_team_id, "away_team_id": m1.away_team_id},
            {"id": m2.id, "home_team_id": m2.home_team_id, "away_team_id": m2.away_team_id},
        ],
    }


@route.post("/advance/{league_id}")
def advance_playoffs(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    After semifinals exist (and possibly scored), create FINAL and THIRD-PLACE matches.
    Tie/winner missing => advance higher seed by current tiebreaker order.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    base = current_week_label()
    week_sf = f"{base}-PO-SF"
    week_final = f"{base}-PO-FINAL"
    week_third = f"{base}-PO-THIRD"

    semis = (
        db.query(models.Match)
        .filter(models.Match.league_id == league_id, models.Match.week == week_sf)
        .order_by(models.Match.id.asc())
        .all()
    )
    if len(semis) < 2:
        raise HTTPException(status_code=400, detail="Semifinals not found. Generate playoffs first.")

    # Determine winners with seed tiebreak if needed
    seed_order = _seed_order_by_tiebreakers(db, league_id)  # full order
    seed_rank = {tid: i for i, tid in enumerate(seed_order, start=1)}  # team_id -> seed #

    def winner_of(m: models.Match) -> int:
        if m.winner_team_id:
            return m.winner_team_id
        # If tied or not scored, pick higher seed (lower number)
        a, b = m.home_team_id, m.away_team_id
        sa, sb = seed_rank.get(a, 999), seed_rank.get(b, 999)
        return a if sa < sb else b

    w1 = winner_of(semis[0])
    w2 = winner_of(semis[1])
    l1 = semis[0].away_team_id if w1 == semis[0].home_team_id else semis[0].home_team_id
    l2 = semis[1].away_team_id if w2 == semis[1].home_team_id else semis[1].home_team_id

    # Avoid duplicates
    already_final = (
        db.query(models.Match).filter(models.Match.league_id == league_id, models.Match.week == week_final).count()
    )
    already_third = (
        db.query(models.Match).filter(models.Match.league_id == league_id, models.Match.week == week_third).count()
    )
    created = []

    if not already_final:
        mf = models.Match(league_id=league_id, week=week_final, home_team_id=w1, away_team_id=w2)
        db.add(mf)
        created.append(("final", mf))
    if not already_third:
        mt = models.Match(league_id=league_id, week=week_third, home_team_id=l1, away_team_id=l2)
        db.add(mt)
        created.append(("third", mt))

    if created:
        db.commit()
        for _, m in created:
            db.refresh(m)

    final = db.query(models.Match).filter(models.Match.league_id == league_id, models.Match.week == week_final).first()
    third = db.query(models.Match).filter(models.Match.league_id == league_id, models.Match.week == week_third).first()
    return {
        "final": None
        if not final
        else {
            "id": final.id,
            "home_team_id": final.home_team_id,
            "away_team_id": final.away_team_id,
        },
        "third_place": None
        if not third
        else {
            "id": third.id,
            "home_team_id": third.home_team_id,
            "away_team_id": third.away_team_id,
        },
    }


@route.get("/{league_id}")
def get_playoffs(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return all playoff matches (SF/FINAL/THIRD) for the current base week."""
    base = current_week_label()
    weeks = [f"{base}-PO-SF", f"{base}-PO-FINAL", f"{base}-PO-THIRD"]
    out: dict[str, Any] = {}
    for w in weeks:
        ms = (
            db.query(models.Match)
            .filter(models.Match.league_id == league_id, models.Match.week == w)
            .order_by(models.Match.id.asc())
            .all()
        )
        out[w] = [{"id": m.id, "home_team_id": m.home_team_id, "away_team_id": m.away_team_id} for m in ms]
    return out
