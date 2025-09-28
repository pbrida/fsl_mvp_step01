# fantasy_stocks/routers/season.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services.periods import current_week_label
from .playoffs import _seed_order_by_tiebreakers  # seeds teams using your tiebreakers

# Reuse helpers from existing routers
from .standings import _score_league_for_period

router = APIRouter(prefix="/season", tags=["season"])


# ---------- Week helpers (regular + playoffs) ----------


def _earliest_unscored_week(db: Session, league_id: int) -> str | None:
    """
    Any week label (regular or playoff) that has at least one unscored match.
    Return the lexicographically earliest label to keep things deterministic.
    """
    rows = (
        db.query(models.Match.week)
        .filter(
            models.Match.league_id == league_id,
            or_(models.Match.home_points.is_(None), models.Match.away_points.is_(None)),
        )
        .distinct()
        .all()
    )
    if not rows:
        return None
    weeks = [w[0] for w in rows]
    weeks.sort()
    return weeks[0]


def _find_weeks_like_suffix(db: Session, league_id: int, suffix: str) -> list[str]:
    """Return distinct week labels that end with the given suffix, e.g. '-PO-SF', '-PO-F', '-PO-3P'."""
    rows = (
        db.query(models.Match.week)
        .filter(models.Match.league_id == league_id, models.Match.week.like(f"%{suffix}"))
        .distinct()
        .all()
    )
    return [w[0] for w in rows]


def _get_matches_for_week(db: Session, league_id: int, week: str) -> list[models.Match]:
    return (
        db.query(models.Match)
        .filter(and_(models.Match.league_id == league_id, models.Match.week == week))
        .all()
    )


def _are_all_scored(ms: list[models.Match]) -> bool:
    return all(m.home_points is not None and m.away_points is not None for m in ms)


# ---------- Semifinals (generate & query) ----------


def _ensure_semifinals(db: Session, league_id: int) -> dict[str, Any]:
    """
    Ensure two semifinal matches exist. If they already exist, return them.
    Otherwise, create with seeds: 1v4 and 2v3 (home is higher seed).
    Week label uses current week base to stay unique: '<current>-PO-SF'.
    """
    exist_weeks = _find_weeks_like_suffix(db, league_id, "-PO-SF")
    if exist_weeks:
        week_sf = sorted(exist_weeks)[0]
        semis = _get_matches_for_week(db, league_id, week_sf)
        return {
            "week": week_sf,
            "semifinals": [
                {"id": m.id, "home_team_id": m.home_team_id, "away_team_id": m.away_team_id}
                for m in semis
            ],
        }

    seeds: list[int] = _seed_order_by_tiebreakers(db, league_id)
    if len(seeds) < 4:
        raise HTTPException(status_code=400, detail="Need at least 4 teams for playoffs")

    s1, s2, s3, s4 = seeds[:4]
    base = current_week_label()
    week_sf = f"{base}-PO-SF"

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


def _winners_and_losers_of_semis(
    db: Session, league_id: int
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """
    Return ((winnerA, winnerB),(loserA, loserB)) if both semifinals exist and are scored; else None.
    """
    weeks = _find_weeks_like_suffix(db, league_id, "-PO-SF")
    if not weeks:
        return None
    week_sf = sorted(weeks)[0]
    semis = _get_matches_for_week(db, league_id, week_sf)
    if len(semis) < 2 or not _are_all_scored(semis):
        return None

    def _winner_loser(m: models.Match) -> tuple[int, int]:
        hp = float(m.home_points or 0.0)
        ap = float(m.away_points or 0.0)
        # Prefer explicit winner if set
        if m.winner_team_id is not None:
            win = m.winner_team_id
            lose = m.away_team_id if win == m.home_team_id else m.home_team_id
            return win, lose
        # Tie fallback: give it to home as winner
        if hp == ap:
            return m.home_team_id, m.away_team_id
        return (m.home_team_id, m.away_team_id) if hp > ap else (m.away_team_id, m.home_team_id)

    w1, l1 = _winner_loser(semis[0])
    w2, l2 = _winner_loser(semis[1])
    return ((w1, w2), (l1, l2))


# ---------- Finals & Bronze (generate, query, champion) ----------


def _ensure_finals(db: Session, league_id: int) -> dict[str, Any]:
    """
    If finals exist, return meta; else, create finals using winners of semis.
    Home team is the higher seed among the two finalists.
    """
    exist_weeks = _find_weeks_like_suffix(db, league_id, "-PO-F")
    if exist_weeks:
        week_f = sorted(exist_weeks)[0]
        fm = _get_matches_for_week(db, league_id, week_f)
        if len(fm) != 1:
            raise HTTPException(status_code=500, detail="Unexpected finals configuration")
        fm = fm[0]
        return {
            "week": week_f,
            "final": {
                "id": fm.id,
                "home_team_id": fm.home_team_id,
                "away_team_id": fm.away_team_id,
            },
        }

    res = _winners_and_losers_of_semis(db, league_id)
    if not res:
        raise HTTPException(status_code=400, detail="Semifinals not decided")
    (wA, wB), _ = res

    seeds: list[int] = _seed_order_by_tiebreakers(db, league_id)
    rank = {tid: i for i, tid in enumerate(seeds, start=1)}
    home, away = (wA, wB) if rank.get(wA, 9999) < rank.get(wB, 9999) else (wB, wA)

    base = current_week_label()
    week_f = f"{base}-PO-F"
    fm = models.Match(league_id=league_id, week=week_f, home_team_id=home, away_team_id=away)
    db.add(fm)
    db.commit()
    db.refresh(fm)
    return {
        "week": week_f,
        "final": {"id": fm.id, "home_team_id": fm.home_team_id, "away_team_id": fm.away_team_id},
    }


def _ensure_bronze(db: Session, league_id: int) -> dict[str, Any]:
    """
    If bronze match exists, return it; else, create bronze using semifinal losers.
    Home team is the higher seed among the two losers.
    """
    exist_weeks = _find_weeks_like_suffix(db, league_id, "-PO-3P")
    if exist_weeks:
        week_b = sorted(exist_weeks)[0]
        ms = _get_matches_for_week(db, league_id, week_b)
        if len(ms) != 1:
            raise HTTPException(status_code=500, detail="Unexpected bronze configuration")
        m = ms[0]
        return {
            "week": week_b,
            "bronze": {"id": m.id, "home_team_id": m.home_team_id, "away_team_id": m.away_team_id},
        }

    res = _winners_and_losers_of_semis(db, league_id)
    if not res:
        raise HTTPException(status_code=400, detail="Semifinals not decided")
    _, (lA, lB) = res

    seeds: list[int] = _seed_order_by_tiebreakers(db, league_id)
    rank = {tid: i for i, tid in enumerate(seeds, start=1)}
    home, away = (lA, lB) if rank.get(lA, 9999) < rank.get(lB, 9999) else (lB, lA)

    base = current_week_label()
    week_b = f"{base}-PO-3P"
    bm = models.Match(league_id=league_id, week=week_b, home_team_id=home, away_team_id=away)
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return {
        "week": week_b,
        "bronze": {"id": bm.id, "home_team_id": bm.home_team_id, "away_team_id": bm.away_team_id},
    }


def _finals_state(db: Session, league_id: int) -> dict[str, Any] | None:
    weeks = _find_weeks_like_suffix(db, league_id, "-PO-F")
    if not weeks:
        return None
    week_f = sorted(weeks)[0]
    fm = _get_matches_for_week(db, league_id, week_f)
    if len(fm) != 1:
        return None
    m = fm[0]
    scored = m.home_points is not None and m.away_points is not None
    return {"week": week_f, "match": m, "scored": scored}


def _champion_from_finals_state(
    state: dict[str, Any], league_id: int, db: Session
) -> dict[str, Any] | None:
    m: models.Match = state["match"]
    if not state["scored"]:
        return None

    if m.winner_team_id is not None:
        champ_id = m.winner_team_id
    else:
        # Tie fallback: higher seed among finalists
        seeds: list[int] = _seed_order_by_tiebreakers(db, league_id)
        rank = {tid: i for i, tid in enumerate(seeds, start=1)}
        champ_id = (
            m.home_team_id
            if rank.get(m.home_team_id, 9999) < rank.get(m.away_team_id, 9999)
            else m.away_team_id
        )

    champ = db.get(models.Team, champ_id)
    return {
        "champion_team_id": champ_id,
        "champion_team_name": champ.name if champ else f"Team {champ_id}",
        "finals_week": state["week"],
        "finals_match_id": m.id,
    }


# ---------- State computation ----------


def _compute_state(db: Session, league_id: int) -> str:
    """
    Returns one of: 'regular' | 'semis' | 'finals' | 'complete'
    """
    finals = _finals_state(db, league_id)
    if finals is not None and finals["scored"]:
        return "complete"
    # finals exist but unscored
    weeks_f = _find_weeks_like_suffix(db, league_id, "-PO-F")
    if weeks_f:
        return "finals"
    # semis exist
    weeks_sf = _find_weeks_like_suffix(db, league_id, "-PO-SF")
    if weeks_sf:
        return "semis"
    return "regular"


# ---------- Public endpoints ----------


@router.get("/{league_id}/state")
def season_state(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return {"ok": True, "league_id": league_id, "state": _compute_state(db, league_id)}


def _team_name(db: Session, team_id: int) -> str:
    t = db.get(models.Team, team_id)
    return t.name if t else f"Team {team_id}"


def _serialize_match(db: Session, m: models.Match) -> dict[str, Any]:
    return {
        "id": m.id,
        "week": m.week,
        "home_team_id": m.home_team_id,
        "home_team_name": _team_name(db, m.home_team_id),
        "away_team_id": m.away_team_id,
        "away_team_name": _team_name(db, m.away_team_id),
        "home_points": None if m.home_points is None else float(m.home_points),
        "away_points": None if m.away_points is None else float(m.away_points),
        "winner_team_id": m.winner_team_id,
    }


@router.get("/{league_id}/bracket")
def season_bracket(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Read-only bracket view for clients to render the playoff tree:
    {
      ok, state, seeds: [team_ids...],
      semifinals_week, semifinals: [match...],
      bronze_week, bronze: match|None,
      finals_week, finals: match|None,
      champion: {team_id, team_name}|None
    }
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    state = _compute_state(db, league_id)
    seeds: list[int] = _seed_order_by_tiebreakers(db, league_id)

    # Semis
    sf_weeks = _find_weeks_like_suffix(db, league_id, "-PO-SF")
    semifinals_week = sorted(sf_weeks)[0] if sf_weeks else None
    semifinals: list[dict[str, Any]] = []
    if semifinals_week:
        for m in _get_matches_for_week(db, league_id, semifinals_week):
            semifinals.append(_serialize_match(db, m))

    # Bronze
    br_weeks = _find_weeks_like_suffix(db, league_id, "-PO-3P")
    bronze_week = sorted(br_weeks)[0] if br_weeks else None
    bronze: dict[str, Any] | None = None
    if bronze_week:
        ms = _get_matches_for_week(db, league_id, bronze_week)
        if ms:
            bronze = _serialize_match(db, ms[0])

    # Finals
    f_state = _finals_state(db, league_id)
    finals_week = f_state["week"] if f_state else None
    finals = _serialize_match(db, f_state["match"]) if f_state else None

    # Champion (if decided)
    champion_meta = _champion_from_finals_state(f_state, league_id, db) if f_state else None
    champion = None
    if champion_meta:
        champion = {
            "team_id": champion_meta["champion_team_id"],
            "team_name": champion_meta["champion_team_name"],
        }

    return {
        "ok": True,
        "league_id": league_id,
        "state": state,
        "seeds": seeds,
        "semifinals_week": semifinals_week,
        "semifinals": semifinals,
        "bronze_week": bronze_week,
        "bronze": bronze,
        "finals_week": finals_week,
        "finals": finals,
        "champion": champion,
    }


@router.post("/{league_id}/advance")
def advance_season(league_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    One-click commissioner flow:
      1) If there are unscored weeks (regular or playoff), score the earliest one.
      2) Else, if semifinals don't exist, create them (top-4 by tiebreakers).
      3) Else, if semis are scored but finals/bronze don't exist, create both.
      4) Else, if finals exist:
           - if unscored, return idle_final_pending
           - if scored, return season_complete + champion
      5) Else idle.

    Every response includes "state": "regular" | "semis" | "finals" | "complete".
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # No matches at all?
    total_matches = db.query(models.Match).filter(models.Match.league_id == league_id).count()
    if total_matches == 0:
        return {
            "ok": True,
            "action": "idle",
            "reason": "no matches",
            "state": _compute_state(db, league_id),
        }

    # 1) Score earliest unscored week (covers regular season, bronze, finals, semis)
    wk = _earliest_unscored_week(db, league_id)
    if wk is not None:
        before = (
            db.query(models.Match)
            .filter(
                models.Match.league_id == league_id,
                models.Match.week == wk,
                models.Match.home_points.isnot(None),
                models.Match.away_points.isnot(None),
            )
            .count()
        )
        _score_league_for_period(db, league, wk)
        after = (
            db.query(models.Match)
            .filter(
                models.Match.league_id == league_id,
                models.Match.week == wk,
                models.Match.home_points.isnot(None),
                models.Match.away_points.isnot(None),
            )
            .count()
        )
        return {
            "ok": True,
            "action": "scored_week",
            "week": wk,
            "matches_scored": max(0, after - before),
            "state": _compute_state(db, league_id),
        }

    # 2) Create semifinals if none exist
    semis_exist = _find_weeks_like_suffix(db, league_id, "-PO-SF")
    if not semis_exist:
        semis = _ensure_semifinals(db, league_id)
        semis.update(
            {"ok": True, "action": "generated_playoffs", "state": _compute_state(db, league_id)}
        )
        return semis

    # 3) If semis are scored but finals/bronze don't exist, create both
    finals_state = _finals_state(db, league_id)
    bronze_exist = _find_weeks_like_suffix(db, league_id, "-PO-3P")
    if finals_state is None or not bronze_exist:
        # Only proceed if semis are decided
        res = _winners_and_losers_of_semis(db, league_id)
        if res:
            out: dict[str, Any] = {"ok": True, "action": "generated_finals_and_bronze"}
            if finals_state is None:
                out.update(_ensure_finals(db, league_id))
            if not bronze_exist:
                out.update(_ensure_bronze(db, league_id))
            out["state"] = _compute_state(db, league_id)
            return out
        # Semis exist but not decided
        return {"ok": True, "action": "idle_semis_pending", "state": _compute_state(db, league_id)}

    # 4) Finals exist
    if not finals_state["scored"]:
        # Finals are waiting to be scored (next call will score them)
        meta = finals_state
        m = meta["match"]
        return {
            "ok": True,
            "action": "idle_final_pending",
            "week": meta["week"],
            "final": {"id": m.id, "home_team_id": m.home_team_id, "away_team_id": m.away_team_id},
            "state": _compute_state(db, league_id),
        }

    # Finals scored => champion
    champ = _champion_from_finals_state(finals_state, league_id, db)
    resp = {"ok": True, "action": "season_complete", **(champ or {})}
    resp["state"] = _compute_state(db, league_id)
    return resp
