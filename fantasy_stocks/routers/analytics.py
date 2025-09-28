# fantasy_stocks/routers/analytics.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _teams_in_league(db: Session, league_id: int) -> list[models.Team]:
    return db.query(models.Team).filter(models.Team.league_id == league_id).order_by(models.Team.id.asc()).all()


def _scored_matches(db: Session, league_id: int) -> list[models.Match]:
    return (
        db.query(models.Match)
        .filter(
            models.Match.league_id == league_id,
            models.Match.home_points.isnot(None),
            models.Match.away_points.isnot(None),
        )
        .order_by(models.Match.id.asc())
        .all()
    )


@router.get("/{league_id}/h2h_matrix")
def h2h_matrix(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Return a head-to-head matrix for the league, summarizing results between every pair of teams.

    Shape:
    {
      ok: true,
      league_id: int,
      teams: [{team_id, team_name}, ...] (N entries, sorted by team_id asc),
      matrix: [
        [ { gp,w,l,t,pf,pa }, ... N cols ... ],
        ...
        N rows ...
      ]
      # matrix[i][j] aggregates games where teams[i] faced teams[j]
      # diagonal i==j is zero row {gp:0,w:0,l:0,t:0,pf:0,pa:0}
    }
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = _teams_in_league(db, league_id)
    if not teams:
        return {"ok": True, "league_id": league_id, "teams": [], "matrix": []}

    idx_by_id = {t.id: i for i, t in enumerate(teams)}
    N = len(teams)

    def zero() -> dict[str, float]:
        return {"gp": 0.0, "w": 0.0, "l": 0.0, "t": 0.0, "pf": 0.0, "pa": 0.0}

    # Initialize N x N matrix of zeros
    M: list[list[dict[str, float]]] = [[zero() for _ in range(N)] for _ in range(N)]

    for m in _scored_matches(db, league_id):
        a = idx_by_id.get(m.home_team_id)
        b = idx_by_id.get(m.away_team_id)
        if a is None or b is None:
            continue

        hp = float(m.home_points or 0.0)
        ap = float(m.away_points or 0.0)

        # a vs b
        M[a][b]["gp"] += 1.0
        M[a][b]["pf"] += hp
        M[a][b]["pa"] += ap
        # b vs a (mirror)
        M[b][a]["gp"] += 1.0
        M[b][a]["pf"] += ap
        M[b][a]["pa"] += hp

        if hp > ap:
            M[a][b]["w"] += 1.0
            M[b][a]["l"] += 1.0
        elif ap > hp:
            M[b][a]["w"] += 1.0
            M[a][b]["l"] += 1.0
        else:
            M[a][b]["t"] += 1.0
            M[b][a]["t"] += 1.0

    # Zero out diagonals explicitly (safety)
    for i in range(N):
        M[i][i] = {"gp": 0.0, "w": 0.0, "l": 0.0, "t": 0.0, "pf": 0.0, "pa": 0.0}

    return {
        "ok": True,
        "league_id": league_id,
        "teams": [{"team_id": t.id, "team_name": t.name} for t in teams],
        "matrix": M,
    }
