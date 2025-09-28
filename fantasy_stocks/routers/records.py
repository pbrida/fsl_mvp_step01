# fantasy_stocks/routers/records.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/records", tags=["records"])


def _team_name(db: Session, team_id: int) -> str:
    t = db.get(models.Team, team_id)
    return t.name if t else f"Team {team_id}"


def _to_float(x: float | None) -> float:
    return 0.0 if x is None else float(x)


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


def _team_week_high(db: Session, league_id: int) -> dict[str, Any] | None:
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


def _narrowest_win(db: Session, league_id: int) -> dict[str, Any] | None:
    matches = _all_scored_matches(db, league_id)
    wins: list[tuple[models.Match, float]] = []
    for m in matches:
        hp = _to_float(m.home_points)
        ap = _to_float(m.away_points)
        if hp != ap:
            wins.append((m, abs(hp - ap)))
    if not wins:
        return None
    m, mg = min(wins, key=lambda t: t[1])
    out = _serialize_match(db, m)
    out["margin"] = mg
    return out


def _streaks(db: Session, league_id: int) -> dict[str, Any]:
    """
    Compute longest win streak and longest unbeaten (W/T) streak for each team.
    Also return current streaks.
    """
    matches = _all_scored_matches(db, league_id)
    if not matches:
        return {"longest_win_streak": None, "longest_unbeaten_streak": None, "current": []}

    # Build per-team result timelines in chronological order.
    timelines: dict[int, list[str]] = {}
    teams = db.query(models.Team).filter(models.Team.league_id == league_id).all()
    for t in teams:
        timelines[t.id] = []

    for m in matches:
        hp = _to_float(m.home_points)
        ap = _to_float(m.away_points)
        if hp > ap:
            timelines[m.home_team_id].append("W")
            timelines[m.away_team_id].append("L")
        elif ap > hp:
            timelines[m.home_team_id].append("L")
            timelines[m.away_team_id].append("W")
        else:
            timelines[m.home_team_id].append("T")
            timelines[m.away_team_id].append("T")

    def longest_run(seq: list[str], wanted: set[str]) -> int:
        best = cur = 0
        for r in seq:
            if r in wanted:
                cur += 1
                if cur > best:
                    best = cur
            else:
                cur = 0
        return best

    def current_run(seq: list[str]) -> str:
        if not seq:
            return ""
        last = seq[-1]
        n = 0
        for r in reversed(seq):
            if r == last:
                n += 1
            else:
                break
        return f"{last}{n}"

    # Longest across teams
    lw_best = (None, 0)  # (team_id, length)
    lu_best = (None, 0)
    current: list[dict[str, Any]] = []

    for tid, seq in timelines.items():
        lw = longest_run(seq, {"W"})
        lu = longest_run(seq, {"W", "T"})
        if lw > lw_best[1]:
            lw_best = (tid, lw)
        if lu > lu_best[1]:
            lu_best = (tid, lu)
        current.append({"team_id": tid, "team_name": _team_name(db, tid), "streak": current_run(seq)})

    longest_win = (
        None
        if lw_best[0] is None
        else {"team_id": lw_best[0], "team_name": _team_name(db, lw_best[0]), "length": lw_best[1]}
    )
    longest_unbeaten = (
        None
        if lu_best[0] is None
        else {"team_id": lu_best[0], "team_name": _team_name(db, lu_best[0]), "length": lu_best[1]}
    )

    return {
        "longest_win_streak": longest_win,
        "longest_unbeaten_streak": longest_unbeaten,
        "current": current,
    }


@router.get("/{league_id}/all")
def records_all(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Aggregate records for a league:
      - team_week_high: best single-week team score
      - game_total_high: highest combined points in a match
      - blowout_high: largest margin of victory
      - narrowest_win: smallest positive margin
      - longest_win_streak: across history
      - longest_unbeaten_streak: across history
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    team_week_high = _team_week_high(db, league_id)
    game_total_high = _game_total_high(db, league_id)
    blowout_high = _blowout_high(db, league_id)
    narrowest = _narrowest_win(db, league_id)
    streaks = _streaks(db, league_id)

    return {
        "ok": True,
        "league_id": league_id,
        "team_week_high": team_week_high,
        "game_total_high": game_total_high,
        "blowout_high": blowout_high,
        "narrowest_win": narrowest,
        **streaks,
    }
