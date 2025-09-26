# fantasy_stocks/routers/scoring.py
from __future__ import annotations

from typing import Dict, List, TypedDict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..services.periods import current_week_label

router = APIRouter(prefix="/scoring", tags=["scoring"])


def _sum_active_proj_points(db: Session, team_id: int) -> float:
    """
    Sum PROJECTIONS for all active roster slots on a team.
    Missing Security or None proj_points => treat as 0.
    """
    slots = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team_id, models.RosterSlot.is_active.is_(True))
        .all()
    )
    if not slots:
        return 0.0

    symbols = [s.symbol for s in slots]
    sec_map: Dict[str, models.Security] = {
        s.symbol: s
        for s in db.query(models.Security).filter(models.Security.symbol.in_(symbols)).all()
    }
    total = 0.0
    for s in slots:
        sec = sec_map.get(s.symbol)
        if sec and sec.proj_points is not None:
            total += float(sec.proj_points)
    return total


class _ProjCloseResult(TypedDict):
    matches_scored: int
    totals: Dict[int, float]


def _close_week_proj(db: Session, league: models.League, period: str) -> _ProjCloseResult:
    """
    Close all matches in `period` for `league` using projection scoring.
    Persists Match points/winner and TeamScore snapshots.
    Returns dict with matches_scored and totals (team_id -> points).
    """
    matches = (
        db.query(models.Match)
        .filter(models.Match.league_id == league.id, models.Match.week == period)
        .all()
    )

    matches_scored = 0
    totals: Dict[int, float] = {}

    for m in matches:
        # skip if already closed
        if m.home_points is not None and m.away_points is not None:
            # still ensure totals reflect stored values
            totals[m.home_team_id] = float(m.home_points or 0.0)
            totals[m.away_team_id] = float(m.away_points or 0.0)
            continue

        home_pts = _sum_active_proj_points(db, m.home_team_id)
        away_pts = _sum_active_proj_points(db, m.away_team_id)

        m.home_points = home_pts
        m.away_points = away_pts
        if home_pts > away_pts:
            m.winner_team_id = m.home_team_id
        elif away_pts > home_pts:
            m.winner_team_id = m.away_team_id
        else:
            m.winner_team_id = None

        # upsert TeamScore for both teams
        for tid, pts in ((m.home_team_id, home_pts), (m.away_team_id, away_pts)):
            ts = (
                db.query(models.TeamScore)
                .filter(
                    models.TeamScore.league_id == league.id,
                    models.TeamScore.team_id == tid,
                    models.TeamScore.period == period,
                )
                .first()
            )
            if ts:
                ts.points = float(pts)
            else:
                ts = models.TeamScore(
                    league_id=league.id, team_id=tid, period=period, points=float(pts)
                )
                db.add(ts)
            totals[tid] = float(pts)

        matches_scored += 1

    db.commit()
    return {"matches_scored": matches_scored, "totals": totals}


@router.post("/close_week/{league_id}")
def close_week(league_id: int, db: Session = Depends(get_db)):
    """
    Close the current ISO week using **projection** scoring.
    Test expectation: response contains `ok`, `week`, `matches_scored`, and `totals`.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    week = current_week_label()
    result = _close_week_proj(db, league, week)
    return {"ok": True, "week": week, **result}


class _ClosedWeek(TypedDict):
    week: str
    matches_scored: int


@router.post("/simulate_season/{league_id}")
def simulate_season(league_id: int, db: Session = Depends(get_db)):
    """
    Close all **open** weeks for this league (projection scoring).
    Returns `closed_weeks`: a list of weeks that were closed during this call.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Find weeks that still have at least one open match
    week_rows = (
        db.query(models.Match.week)
        .filter(
            models.Match.league_id == league.id,
            (models.Match.home_points.is_(None)) | (models.Match.away_points.is_(None)),
        )
        .distinct()
        .all()
    )
    weeks = sorted({w[0] for w in week_rows})

    closed_weeks: List[_ClosedWeek] = []
    for w in weeks:
        res = _close_week_proj(db, league, w)
        closed_weeks.append({"week": w, "matches_scored": res["matches_scored"]})

    return {"ok": True, "closed_weeks": closed_weeks}
