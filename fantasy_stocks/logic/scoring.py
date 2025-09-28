# fantasy_stocks/logic/scoring.py
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from ..services import pricing


def _active_starter_symbols(db: Session, team_id: int, starters_limit: int | None = None) -> list[str]:
    """
    Return the symbols of active starters for a team, in any stable order.
    If starters_limit is provided, trim to that count.
    """
    q = (
        db.query(models.RosterSlot)
        .filter(models.RosterSlot.team_id == team_id, models.RosterSlot.is_active.is_(True))
        .order_by(models.RosterSlot.id.asc())
    )
    slots = q.all()
    symbols = [s.symbol for s in slots]
    if starters_limit is not None:
        symbols = symbols[:starters_limit]
    return symbols


def _proj_points_for_symbol(db: Session, symbol: str) -> float:
    sec = db.get(models.Security, symbol)
    return float(sec.proj_points or 0.0) if sec else 0.0


def compute_team_points_projections(db: Session, league: models.League, team_id: int) -> float:
    """
    Sum Security.proj_points for the team's active starters (count-limited by league.starters).
    """
    symbols = _active_starter_symbols(db, team_id, starters_limit=league.starters)
    return sum(_proj_points_for_symbol(db, sym) for sym in symbols)


def compute_team_points_live(db: Session, league: models.League, team_id: int, iso_week: str) -> float:
    """
    Sum per-day % changes for each starter over the given ISO week, then sum across starters.
    """
    symbols = _active_starter_symbols(db, team_id, starters_limit=league.starters)
    return sum(pricing.get_week_return_pct(db, sym, iso_week) for sym in symbols)


def close_week(db: Session, league_id: int, iso_week: str) -> None:
    """
    Calculate and persist weekly points for all matches in the given league/week,
    honoring league.scoring_mode. Also updates Match winner & points, and writes TeamScore rows.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise ValueError(f"League {league_id} not found")

    # Fetch all matches for this week
    matches: list[models.Match] = (
        db.query(models.Match)
        .filter(models.Match.league_id == league.id, models.Match.week == iso_week)
        .order_by(models.Match.id.asc())
        .all()
    )

    for m in matches:
        if league.scoring_mode == models.ScoringMode.LIVE:
            home_pts = compute_team_points_live(db, league, m.home_team_id, iso_week)
            away_pts = compute_team_points_live(db, league, m.away_team_id, iso_week)
        else:
            home_pts = compute_team_points_projections(db, league, m.home_team_id)
            away_pts = compute_team_points_projections(db, league, m.away_team_id)

        # Persist TeamScore rows (upsert-ish: keep it simple; assume at most one per (league,team,period))
        for team_id, pts in [(m.home_team_id, home_pts), (m.away_team_id, away_pts)]:
            existing = (
                db.query(models.TeamScore)
                .filter(
                    models.TeamScore.league_id == league.id,
                    models.TeamScore.team_id == team_id,
                    models.TeamScore.period == iso_week,
                )
                .first()
            )
            if existing:
                if existing.points != pts:
                    existing.points = pts
                    db.add(existing)
            else:
                db.add(models.TeamScore(league_id=league.id, team_id=team_id, period=iso_week, points=pts))

        # Update match outcome
        m.home_points = home_pts
        m.away_points = away_pts
        if abs(home_pts - away_pts) < 1e-9:
            m.winner_team_id = None  # tie
        else:
            m.winner_team_id = m.home_team_id if home_pts > away_pts else m.away_team_id
        db.add(m)

    db.commit()


# ----------------------------
# Backward-compat helper names
# ----------------------------


def close_week_with_proj_points(db: Session, league_id: int, iso_week: str) -> None:
    """
    Force-close a week using projections (used by older tests/callers).
    """
    league = db.get(models.League, league_id)
    if not league:
        raise ValueError(f"League {league_id} not found")

    matches: list[models.Match] = (
        db.query(models.Match)
        .filter(models.Match.league_id == league.id, models.Match.week == iso_week)
        .order_by(models.Match.id.asc())
        .all()
    )

    for m in matches:
        home_pts = compute_team_points_projections(db, league, m.home_team_id)
        away_pts = compute_team_points_projections(db, league, m.away_team_id)

        # team score rows
        for team_id, pts in [(m.home_team_id, home_pts), (m.away_team_id, away_pts)]:
            existing = (
                db.query(models.TeamScore)
                .filter(
                    models.TeamScore.league_id == league.id,
                    models.TeamScore.team_id == team_id,
                    models.TeamScore.period == iso_week,
                )
                .first()
            )
            if existing:
                if existing.points != pts:
                    existing.points = pts
                    db.add(existing)
            else:
                db.add(models.TeamScore(league_id=league.id, team_id=team_id, period=iso_week, points=pts))

        m.home_points = home_pts
        m.away_points = away_pts
        if abs(home_pts - away_pts) < 1e-9:
            m.winner_team_id = None
        else:
            m.winner_team_id = m.home_team_id if home_pts > away_pts else m.away_team_id
        db.add(m)

    db.commit()


def simulate_season_with_proj_points(db: Session, league_id: int) -> None:
    """
    Iterate all distinct weeks in the league's schedule and close each using projections.
    (Compatibility shim for older code.)
    """
    league = db.get(models.League, league_id)
    if not league:
        raise ValueError(f"League {league_id} not found")

    weeks: list[str] = [
        w
        for (w,) in db.query(models.Match.week)
        .filter(models.Match.league_id == league.id)
        .distinct()
        .order_by(models.Match.week.asc())
        .all()
    ]
    for wk in weeks:
        close_week_with_proj_points(db, league_id, wk)
