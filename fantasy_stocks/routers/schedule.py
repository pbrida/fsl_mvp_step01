# fantasy_stocks/routers/schedule.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services.periods import current_week_label

# NOTE: This keeps your original prefix & tag so existing tests keep passing.
route = APIRouter(prefix="/schedule", tags=["schedule"])


def _pair_round(team_ids: list[int]) -> list[tuple[int, int]]:
    """
    Pair teams in order (1v2, 3v4, ...) for a single round.
    Assumes an even list; caller handles odd cases (bye).
    Home/away assignment is done by caller.
    """
    pairs: list[tuple[int, int]] = []
    for i in range(0, len(team_ids), 2):
        a = team_ids[i]
        b = team_ids[i + 1]
        pairs.append((a, b))
    return pairs


@route.post("/generate/{league_id}")
def generate_week(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    ORIGINAL single-week generator that your existing tests call.
    Creates matchups for the CURRENT ISO week label (no duplicates if already exists).
    Pairs teams in order; alternates home/away by index for a bit of variety.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = (
        db.query(models.Team)
        .filter(models.Team.league_id == league_id)
        .order_by(models.Team.id.asc())
        .all()
    )
    if len(teams) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 teams")

    week = current_week_label()

    # If matches for this exact week already exist, do nothing (idempotent).
    already = (
        db.query(models.Match)
        .filter(models.Match.league_id == league_id, models.Match.week == week)
        .count()
    )
    if already:
        return {"ok": True, "week": week, "matches_created": 0}

    ids = [t.id for t in teams]
    if len(ids) % 2 == 1:
        # Odd count -> drop the last one for this week (simple bye)
        ids = ids[:-1]

    pairs = _pair_round(ids)

    created = 0
    for idx, (a, b) in enumerate(pairs):
        # alternate home/away
        if idx % 2 == 0:
            home, away = a, b
        else:
            home, away = b, a
        m = models.Match(league_id=league_id, week=week, home_team_id=home, away_team_id=away)
        db.add(m)
        created += 1

    db.commit()
    return {"ok": True, "week": week, "matches_created": created}


@route.post("/season/{league_id}")
def generate_season(
    league_id: int, weeks: int = 0, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Generate a season schedule using the "circle method" round-robin.
    - If weeks <= 0: generate a single round-robin (n-1 rounds).
    - Weeks are labeled based on the *current week* with a +WkN suffix to avoid collisions
      with your existing /schedule/generate week.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = (
        db.query(models.Team)
        .filter(models.Team.league_id == league_id)
        .order_by(models.Team.id.asc())
        .all()
    )
    n = len(teams)
    if n < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 teams")

    ids = [t.id for t in teams]

    # If odd n, add a bye marker (0)
    if n % 2 == 1:
        ids.append(0)
        n += 1

    # Round count
    rounds = n - 1 if weeks <= 0 else weeks

    base = current_week_label()
    created_matches = 0
    created_weeks = set()

    # Circle method with first element fixed
    arr = ids[:]
    for rnd in range(rounds):
        # Create pairs for this round
        pairs: list[tuple[int, int]] = []
        for i in range(n // 2):
            a = arr[i]
            b = arr[-(i + 1)]
            if a == 0 or b == 0:
                continue
            # Alternate home/away each round
            if rnd % 2 == 0:
                pairs.append((a, b))
            else:
                pairs.append((b, a))

        week_label = f"{base}+Wk{rnd + 1}"

        # Avoid duplicate creation if this week already exists
        existing = (
            db.query(models.Match)
            .filter(models.Match.league_id == league_id, models.Match.week == week_label)
            .count()
        )
        if existing == 0:
            for h, a in pairs:
                m = models.Match(
                    league_id=league_id, week=week_label, home_team_id=h, away_team_id=a
                )
                db.add(m)
                created_matches += 1
            if pairs:
                created_weeks.add(week_label)

        # Rotate (keep first fixed)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]

    db.commit()
    return {
        "ok": True,
        "weeks_created": len(created_weeks),
        "matches_created": created_matches,
    }


@route.get("/{league_id}/weeks")
def list_weeks(league_id: int, db: Session = Depends(get_db)) -> list[str]:
    """
    List distinct week labels for a league in ascending order.
    Includes both normal weeks and playoff/season labels.
    """
    weeks = db.query(models.Match.week).filter(models.Match.league_id == league_id).distinct().all()
    return sorted([w[0] for w in weeks])
