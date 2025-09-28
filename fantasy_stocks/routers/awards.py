# fantasy_stocks/routers/awards.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/awards", tags=["awards"])


# ---------- Helpers (null-safe floats, names, latest period) ----------


def _to_float(x: float | None) -> float:
    return 0.0 if x is None else float(x)


def _team_name(db: Session, team_id: int) -> str:
    t = db.get(models.Team, team_id)
    return t.name if t else f"Team {team_id}"


def _latest_scored_period(db: Session, league_id: int) -> str | None:
    row = (
        db.query(models.TeamScore.period)
        .filter(models.TeamScore.league_id == league_id)
        .order_by(models.TeamScore.period.desc())
        .first()
    )
    return row[0] if row else None


def _serialize_match(db: Session, m: models.Match) -> dict[str, Any]:
    return {
        "id": m.id,
        "week": m.week,
        "home_team_id": m.home_team_id,
        "home_team_name": _team_name(db, m.home_team_id),
        "home_points": None if m.home_points is None else float(m.home_points),
        "away_team_id": m.away_team_id,
        "away_team_name": _team_name(db, m.away_team_id),
        "away_points": None if m.away_points is None else float(m.away_points),
        "winner_team_id": m.winner_team_id,
    }


def _matches_for_week(db: Session, league_id: int, period: str) -> list[models.Match]:
    return (
        db.query(models.Match)
        .filter(
            models.Match.league_id == league_id,
            models.Match.week == period,
            models.Match.home_points.isnot(None),
            models.Match.away_points.isnot(None),
        )
        .all()
    )


def _all_scored_matches(db: Session, league_id: int) -> list[models.Match]:
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


def _all_team_scores(db: Session, league_id: int) -> list[models.TeamScore]:
    return (
        db.query(models.TeamScore)
        .filter(models.TeamScore.league_id == league_id)
        .order_by(models.TeamScore.period.asc(), models.TeamScore.team_id.asc())
        .all()
    )


# ---------- Weekly Awards ----------


@router.get("/{league_id}/weekly")
def weekly_awards(
    league_id: int, period: str | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Weekly Awards from scored matches. If 'period' omitted, uses latest scored week.
    Returns: top_scorer, narrowest_win, blowout, highest_scoring_game (or nulls if no data).
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    if period is None:
        period = _latest_scored_period(db, league_id)
        if not period:
            return {
                "ok": True,
                "league_id": league_id,
                "period": None,
                "top_scorer": None,
                "narrowest_win": None,
                "blowout": None,
                "highest_scoring_game": None,
            }

    # Top scorer (from TeamScore for that week)
    rows = (
        db.query(models.TeamScore)
        .filter(models.TeamScore.league_id == league_id, models.TeamScore.period == period)
        .all()
    )
    top = None
    if rows:
        best = max(rows, key=lambda r: _to_float(r.points))
        top = {
            "team_id": best.team_id,
            "team_name": _team_name(db, best.team_id),
            "points": _to_float(best.points),
        }

    matches = _matches_for_week(db, league_id, period)

    # Narrowest & Blowout (only non-tied games)
    narrow = None
    blow = None
    wins: list[tuple[models.Match, float]] = []
    for m in matches:
        hp = _to_float(m.home_points)
        ap = _to_float(m.away_points)
        if hp != ap:
            wins.append((m, abs(hp - ap)))
    if wins:
        nm, _ = min(wins, key=lambda t: t[1])
        bm, _ = max(wins, key=lambda t: t[1])
        narrow = _serialize_match(db, nm)
        blow = _serialize_match(db, bm)

    # Highest-scoring game by total points
    high = None
    if matches:

        def total(m_: models.Match) -> float:
            return _to_float(m_.home_points) + _to_float(m_.away_points)

        hm = max(matches, key=total)
        high = _serialize_match(db, hm)

    return {
        "ok": True,
        "league_id": league_id,
        "period": period,
        "top_scorer": top,
        "narrowest_win": narrow,
        "blowout": blow,
        "highest_scoring_game": high,
    }


# ---------- Season Awards ----------


def _aggregate_season_stats(db: Session, league_id: int) -> dict[int, dict[str, float]]:
    """
    Aggregate PF/PA, wins/losses/ties, games_played per team from scored matches.
    Returns { team_id: {pf, pa, w, l, t, gp, win_pct, point_diff} }
    """
    stats: dict[int, dict[str, float]] = {}
    # Initialize for all teams (so teams with 0 games still appear, with 0s)
    for t in db.query(models.Team).filter(models.Team.league_id == league_id).all():
        stats[t.id] = {
            "pf": 0.0,
            "pa": 0.0,
            "w": 0.0,
            "l": 0.0,
            "t": 0.0,
            "gp": 0.0,
            "win_pct": 0.0,
            "point_diff": 0.0,
        }

    for m in _all_scored_matches(db, league_id):
        hp = _to_float(m.home_points)
        ap = _to_float(m.away_points)
        a = stats[m.home_team_id]
        b = stats[m.away_team_id]
        a["gp"] += 1
        b["gp"] += 1
        a["pf"] += hp
        a["pa"] += ap
        b["pf"] += ap
        b["pa"] += hp
        if hp > ap:
            a["w"] += 1
            b["l"] += 1
        elif ap > hp:
            b["w"] += 1
            a["l"] += 1
        else:
            a["t"] += 1
            b["t"] += 1

    # finalize
    for rec in stats.values():
        gp = rec["gp"]
        rec["point_diff"] = rec["pf"] - rec["pa"]
        rec["win_pct"] = (rec["w"] + 0.5 * rec["t"]) / gp if gp > 0 else 0.0

    return stats


def _team_week_high(db: Session, league_id: int) -> dict[str, Any] | None:
    """Best single-week TeamScore."""
    rows = _all_team_scores(db, league_id)
    if not rows:
        return None
    best = max(rows, key=lambda r: _to_float(r.points))
    return {
        "team_id": best.team_id,
        "team_name": _team_name(db, best.team_id),
        "period": best.period,
        "points": _to_float(best.points),
    }


def _game_total_high(db: Session, league_id: int) -> dict[str, Any] | None:
    matches = _all_scored_matches(db, league_id)
    if not matches:
        return None

    def total(m: models.Match) -> float:
        return _to_float(m.home_points) + _to_float(m.away_points)

    m = max(matches, key=total)
    out = _serialize_match(db, m)
    out["total_points"] = total(m)
    return out


def _blowout_high(db: Session, league_id: int) -> dict[str, Any] | None:
    matches = _all_scored_matches(db, league_id)
    if not matches:
        return None

    def margin(m: models.Match) -> float:
        return abs(_to_float(m.home_points) - _to_float(m.away_points))

    m = max(matches, key=margin)
    out = _serialize_match(db, m)
    out["margin"] = margin(m)
    return out


@router.get("/{league_id}/season")
def season_awards(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Season Awards (regular season to date), derived from scored matches.

    Returns:
    {
      ok, league_id,
      winningest_team: {team_id, team_name, win_pct, point_diff} | null,
      mvp_offense:     {team_id, team_name, points_for} | null,
      best_defense:    {team_id, team_name, points_against} | null,
      highest_single_week_team: {...} | null,  # from TeamScore
      highest_scoring_game: {...} | null,      # match + total_points
      biggest_blowout: {...} | null            # match + margin
    }
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    stats = _aggregate_season_stats(db, league_id)
    if not stats:
        return {
            "ok": True,
            "league_id": league_id,
            "winningest_team": None,
            "mvp_offense": None,
            "best_defense": None,
            "highest_single_week_team": None,
            "highest_scoring_game": None,
            "biggest_blowout": None,
        }

    # winningest by (win_pct, point_diff)
    winningest_tid = max(
        stats.keys(), key=lambda tid: (stats[tid]["win_pct"], stats[tid]["point_diff"])
    )
    winningest = {
        "team_id": winningest_tid,
        "team_name": _team_name(db, winningest_tid),
        "win_pct": stats[winningest_tid]["win_pct"],
        "point_diff": stats[winningest_tid]["point_diff"],
    }

    # MVP offense: highest total PF
    mvp_tid = max(stats.keys(), key=lambda tid: stats[tid]["pf"])
    mvp = {
        "team_id": mvp_tid,
        "team_name": _team_name(db, mvp_tid),
        "points_for": stats[mvp_tid]["pf"],
    }

    # Best defense: lowest total PA (require gp>0 to be fair)
    eligible = [tid for tid, rec in stats.items() if rec["gp"] > 0]
    bestd = None
    if eligible:
        bd_tid = min(eligible, key=lambda tid: stats[tid]["pa"])
        bestd = {
            "team_id": bd_tid,
            "team_name": _team_name(db, bd_tid),
            "points_against": stats[bd_tid]["pa"],
        }

    highest_week = _team_week_high(db, league_id)
    high_game = _game_total_high(db, league_id)
    blowout = _blowout_high(db, league_id)

    return {
        "ok": True,
        "league_id": league_id,
        "winningest_team": winningest,
        "mvp_offense": mvp,
        "best_defense": bestd,
        "highest_single_week_team": highest_week,
        "highest_scoring_game": high_game,
        "biggest_blowout": blowout,
    }
