# fantasy_stocks/routers/standings.py
from __future__ import annotations

from typing import List, Dict, TypedDict, Optional, Set, Tuple
from collections import defaultdict
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models, schemas
from ..services.periods import current_week_label
from ..utils.num import to_float
from ..utils.idempotency import with_idempotency


route = APIRouter(prefix="/standings", tags=["standings"])


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
    total = 0.0
    if not slots:
        return total
    symbols = [s.symbol for s in slots]
    # fetch all securities once
    sec_map: Dict[str, models.Security] = {
        s.symbol: s
        for s in db.query(models.Security).filter(models.Security.symbol.in_(symbols)).all()
    }
    for s in slots:
        sec = sec_map.get(s.symbol)
        # 👇 use to_float to safely handle None / missing
        total += to_float(getattr(sec, "proj_points", None))
    return total


def _score_league_for_period(db: Session, league: models.League, period: str) -> List[schemas.ScoreOut]:
    """
    Score all matches for a league in a given ISO week `period` using PROJECTIONS stub:
    points = sum of proj_points for active starters.
    Persists Match.home_points/away_points, winner, and TeamScore snapshots.
    """
    matches = (
        db.query(models.Match)
        .filter(
            models.Match.league_id == league.id,
            models.Match.week == period,
        )
        .all()
    )

    out: List[schemas.ScoreOut] = []
    if not matches:
        return out

    for m in matches:
        # already scored? skip
        if m.home_points is not None and m.away_points is not None:
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
            m.winner_team_id = None  # tie

        # upsert TeamScore rows
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
                ts.points = pts
            else:
                ts = models.TeamScore(
                    league_id=league.id, team_id=tid, period=period, points=pts
                )
                db.add(ts)

        # accumulate response with safe team-name fallback
        home_team = db.get(models.Team, m.home_team_id)
        away_team = db.get(models.Team, m.away_team_id)
        home_name = home_team.name if home_team else f"Team {m.home_team_id}"
        away_name = away_team.name if away_team else f"Team {m.away_team_id}"

        out.append(schemas.ScoreOut(team_id=m.home_team_id, team_name=home_name, period=period, points=home_pts))
        out.append(schemas.ScoreOut(team_id=m.away_team_id, team_name=away_name, period=period, points=away_pts))

    db.commit()
    return out


@route.post("/{league_id}/close_week", operation_id="standings_close_week")

@with_idempotency("close_week_v1")   # 👈 idempotency decorator
async def close_week(
    league_id: int,
    request: Request,                 # 👈 now a real type, not a forward ref
    db: Session = Depends(get_db),
):
    """
    Close the current ISO week for this league using PROJECTIONS stub scoring.
    Returns { ok, week, matches_scored, totals } where totals is { team_id: points }.
    Requires an Idempotency-Key header to avoid double-scoring on retries.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    week = current_week_label()
    results = _score_league_for_period(db, league, week)

    # Each match contributes two ScoreOut entries (home+away), so // 2
    matches_scored = len(results) // 2

    # Build totals dict the tests expect (team_id -> points for the week)
    totals: Dict[int, float] = {}
    for r in results:
        totals[r.team_id] = float(r.points)

    return {"ok": True, "week": week, "matches_scored": matches_scored, "totals": totals}

@route.post("/{league_id}/close_season", operation_id="standings_close_season")

@with_idempotency("close_season_v1")   # 👈 idempotency decorator
async def close_season(
    league_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Score every week that has matches for this league, using current projections stub.
    Safe to call multiple times; only unscored matches are scored.
    Requires an Idempotency-Key header to avoid double-scoring on retries.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # distinct weeks that have matches
    weeks = (
        db.query(models.Match.week)
        .filter(models.Match.league_id == league_id)
        .distinct()
        .all()
    )
    weeks = [w[0] for w in weeks]
    total_matches_scored = 0

    for wk in weeks:
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
        _ = _score_league_for_period(db, league, wk)
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
        total_matches_scored += max(0, (after - before))

    return {"ok": True, "weeks": weeks, "matches_scored": total_matches_scored}


# TypedDict to make Pylance happy about the mixed types in the accumulator
class _StatRow(TypedDict):
    team_id: int
    team_name: str
    wins: int
    losses: int
    ties: int
    games_played: int
    points_for: float
    points_against: float


def _aggregate_table_rows(db: Session, league_id: int) -> List[schemas.TableRow]:
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = db.query(models.Team).filter(models.Team.league_id == league.id).all()
    if not teams:
        return []

    stat: Dict[int, _StatRow] = {
        t.id: _StatRow(
            team_id=t.id,
            team_name=t.name,
            wins=0,
            losses=0,
            ties=0,
            games_played=0,
            points_for=0.0,
            points_against=0.0,
        )
        for t in teams
    }

    played = (
        db.query(models.Match)
        .filter(
            models.Match.league_id == league.id,
            models.Match.home_points.isnot(None),
            models.Match.away_points.isnot(None),
        )
        .all()
    )
    for m in played:
        hp = to_float(m.home_points)
        ap = to_float(m.away_points)

        h = stat.get(m.home_team_id)
        a = stat.get(m.away_team_id)
        if h is None or a is None:
            continue

        h["games_played"] += 1
        a["games_played"] += 1
        h["points_for"] += hp
        h["points_against"] += ap
        a["points_for"] += ap
        a["points_against"] += hp

        if hp > ap:
            h["wins"] += 1
            a["losses"] += 1
        elif ap > hp:
            a["wins"] += 1
            h["losses"] += 1
        else:
            h["ties"] += 1
            a["ties"] += 1

    table: List[schemas.TableRow] = []
    for t in teams:
        row = stat[t.id]
        gp = int(row["games_played"])
        pf = to_float(row["points_for"])
        pa = to_float(row["points_against"])
        diff = pf - pa
        wins = int(row["wins"])
        ties = int(row["ties"])
        win_pct = (wins + 0.5 * ties) / gp if gp > 0 else 0.0

        table.append(
            schemas.TableRow(
                team_id=t.id,
                team_name=t.name,
                wins=wins,
                losses=int(row["losses"]),
                ties=ties,
                games_played=gp,
                points_for=pf,
                points_against=pa,
                point_diff=diff,
                win_pct=win_pct,
            )
        )

    table.sort(key=lambda r: (r.win_pct, r.point_diff), reverse=True)
    return table


@route.get("/{league_id}", operation_id="standings_get")

def get_standings(league_id: int, persist: bool = False, db: Session = Depends(get_db)):
    """
    Two behaviors (to satisfy tests):
      - If persist=true: return a PLAIN LIST of weekly ScoreOut-like dicts for the latest period:
          [{team_id, team_name, period, points}, ...]
      - Else: return an aggregate standings table WRAPPED in {"ok": true, "table": [...]}
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # persist=true => latest week's per-team points (plain list)
    if persist:
        latest = (
            db.query(models.TeamScore.period)
            .filter(models.TeamScore.league_id == league.id)
            .order_by(models.TeamScore.period.desc())
            .first()
        )
        if not latest:
            return []  # no scores yet
        latest_period = latest[0]

        scores = (
            db.query(models.TeamScore)
            .filter(
                models.TeamScore.league_id == league.id,
                models.TeamScore.period == latest_period,
            )
            .all()
        )

        team_map = {
            t.id: t.name
            for t in db.query(models.Team).filter(models.Team.league_id == league.id).all()
        }

        return [
            {
                "team_id": ts.team_id,
                "team_name": team_map.get(ts.team_id, f"Team {ts.team_id}"),
                "period": ts.period,
                "points": float(ts.points),
            }
            for ts in scores
        ]

    # Default aggregated-with-wrapper
    table = _aggregate_table_rows(db, league_id)
    return {"ok": True, "table": [r.model_dump() for r in table]}


@route.get("/{league_id}/table", operation_id="standings_table")

def standings_table(league_id: int, db: Session = Depends(get_db)):
    """
    Return a PLAIN LIST of aggregate table rows (not wrapped), i.e.:
    [
      {"team_id": ..., "team_name": ..., "wins": ..., "losses": ..., "ties": ...,
       "games_played": ..., "points_for": ..., "points_against": ...,
       "point_diff": ..., "win_pct": ...},
      ...
    ]
    """
    table = _aggregate_table_rows(db, league_id)
    return [r.model_dump() for r in table]


@route.get("/{league_id}/history", operation_id="standings_history")

def standings_history(league_id: int, db: Session = Depends(get_db)):
    """
    Return per-team weekly scoring snapshots from TeamScore.
    Shape: [{team_id, team_name, period, points}, ...] ordered by week then team.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = db.query(models.Team).filter(models.Team.league_id == league.id).all()
    team_name_by_id = {t.id: t.name for t in teams}

    scores = (
        db.query(models.TeamScore)
        .filter(models.TeamScore.league_id == league.id)
        .order_by(models.TeamScore.period.asc(), models.TeamScore.team_id.asc())
        .all()
    )

    history = [
        {
            "team_id": s.team_id,
            "team_name": team_name_by_id.get(s.team_id, f"Team {s.team_id}"),
            "period": s.period,
            "points": float(s.points),
        }
        for s in scores
    ]

    return history


# --- Power Rankings helpers (Pythagorean expectation) ----------------------------

def _pf_pa_by_team(db: Session, league_id: int) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    matches = (
        db.query(models.Match)
        .filter(
            models.Match.league_id == league_id,
            models.Match.home_points.isnot(None),
            models.Match.away_points.isnot(None),
        )
        .all()
    )
    for m in matches:
        hp = to_float(m.home_points)
        ap = to_float(m.away_points)
        out.setdefault(m.home_team_id, {"pf": 0.0, "pa": 0.0})
        out.setdefault(m.away_team_id, {"pf": 0.0, "pa": 0.0})
        out[m.home_team_id]["pf"] += hp
        out[m.home_team_id]["pa"] += ap
        out[m.away_team_id]["pf"] += ap
        out[m.away_team_id]["pa"] += hp
    return out


def _pythag_expectation(pf: float, pa: float, exponent: float = 2.0) -> float:
    """
    Classic Pythagorean expectation: pf^x / (pf^x + pa^x).
    Handles zero gracefully.
    """
    if pf <= 0 and pa <= 0:
        return 0.5
    return (pf ** exponent) / ((pf ** exponent) + (pa ** exponent))


# --- Tiebreakers v1 --------------------------------------------------------------

def _scored_matches_for_league(db: Session, league_id: int) -> List[models.Match]:
    return (
        db.query(models.Match)
        .filter(
            models.Match.league_id == league_id,
            models.Match.home_points.isnot(None),
            models.Match.away_points.isnot(None),
        )
        .all()
    )


def _h2h_stats_among(db: Session, league_id: int, group: Set[int]) -> Dict[int, Dict[str, float]]:
    stats: Dict[int, Dict[str, float]] = {
        tid: {"wins": 0.0, "losses": 0.0, "ties": 0.0, "pf": 0.0, "pa": 0.0}
        for tid in group
    }
    for m in _scored_matches_for_league(db, league_id):
        a, b = m.home_team_id, m.away_team_id
        if a in group and b in group:
            hp = to_float(m.home_points)
            ap = to_float(m.away_points)
            stats[a]["pf"] += hp
            stats[a]["pa"] += ap
            stats[b]["pf"] += ap
            stats[b]["pa"] += hp
            if hp > ap:
                stats[a]["wins"] += 1.0
                stats[b]["losses"] += 1.0
            elif ap > hp:
                stats[b]["wins"] += 1.0
                stats[a]["losses"] += 1.0
            else:
                stats[a]["ties"] += 1.0
                stats[b]["ties"] += 1.0
    return stats

def _deterministic_coin(league_id: int, team_id: int) -> float:
    """
    Stable tie-break shard in [0,1): hash(league_id, team_id) -> float.
    Ensures fully deterministic ordering across runs.
    """
    h = hashlib.sha1(f"{league_id}:{team_id}".encode("utf-8")).hexdigest()
    # use first 8 hex chars -> int -> normalize
    return int(h[:8], 16) / 0xFFFFFFFF


@route.get("/{league_id}/tiebreakers", operation_id="standings_tiebreakers")

def tiebreakers(
    league_id: int,
    team_ids: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Resolve ordering using Tiebreakers v1:
      1) Overall win_pct  (already computed in aggregate table)
      2) Head-to-head mini-league win_pct among tied teams only
      3) Point diff (PF - PA)
      4) Points For (PF)
      5) Deterministic coin (stable hash)

    Query:
      - team_ids: optional comma-separated list of team_ids to evaluate as a group.
                  If omitted, applies to ALL teams in the league.

    Returns: [{ team_id, team_name, win_pct, h2h_win_pct, point_diff, points_for, reason }]
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Base table (overall metrics)
    base = _aggregate_table_rows(db, league_id)  # List[schemas.TableRow], computed from scored matches
    if team_ids:
        want: Set[int] = {int(x) for x in team_ids.split(",") if x.strip()}
        base = [r for r in base if r.team_id in want]

    group_ids: Set[int] = {r.team_id for r in base}
    # Mini-league head-to-head stats only among the considered group
    h2h = _h2h_stats_among(db, league_id, group_ids)

    def key_for(row: schemas.TableRow) -> Tuple:
        # overall
        win_pct = float(row.win_pct or 0.0)
        diff = float(row.point_diff or 0.0)
        pf = float(row.points_for or 0.0)

        # head-to-head within tie group
        hs = h2h.get(row.team_id, {"wins": 0.0, "losses": 0.0, "ties": 0.0})
        g = hs["wins"] + hs["losses"] + hs["ties"]
        h2h_win_pct = (hs["wins"] + 0.5 * hs["ties"]) / g if g > 0 else 0.0

        coin = _deterministic_coin(league_id, row.team_id)
        # Sort by: overall win_pct, h2h, point_diff, points_for, coin
        return (win_pct, h2h_win_pct, diff, pf, coin)

    # Sort and build explanations
    sorted_rows = sorted(base, key=key_for, reverse=True)
    out = []
    for r in sorted_rows:
        hs = h2h.get(r.team_id, {"wins": 0.0, "losses": 0.0, "ties": 0.0})
        g = hs["wins"] + hs["losses"] + hs["ties"]
        h2h_win_pct = (hs["wins"] + 0.5 * hs["ties"]) / g if g > 0 else 0.0
        out.append({
            "team_id": r.team_id,
            "team_name": r.team_name,
            "win_pct": float(r.win_pct),
            "h2h_win_pct": h2h_win_pct,
            "point_diff": float(r.point_diff),
            "points_for": float(r.points_for),
            "reason": "Sorted by win_pct → h2h_win_pct → point_diff → points_for → coin",
        })
    return out


# --- Power Rankings+: SOS, streaks, last-5 --------------------------------------

def _scored_matches(db: Session, league_id: int) -> List[models.Match]:
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


def _pf_pa_per_team(db: Session, league_id: int) -> Dict[int, Dict[str, float]]:
    # PF/PA across all scored matches (overall totals and games played)
    out: Dict[int, Dict[str, float]] = defaultdict(lambda: {"pf": 0.0, "pa": 0.0, "gp": 0})
    for m in _scored_matches(db, league_id):
        hp = float(m.home_points or 0.0)
        ap = float(m.away_points or 0.0)
        out[m.home_team_id]["pf"] += hp
        out[m.home_team_id]["pa"] += ap
        out[m.home_team_id]["gp"] += 1
        out[m.away_team_id]["pf"] += ap
        out[m.away_team_id]["pa"] += hp
        out[m.away_team_id]["gp"] += 1
    return out


def _sos_by_team(db: Session, league_id: int) -> Dict[int, float]:
    """
    SOS = average of opponents' PF-per-game (season-wide), across games played so far.
    (Deterministic and schema-free.)
    """
    pfpa = _pf_pa_per_team(db, league_id)
    matches = _scored_matches(db, league_id)
    # Precompute PF/game for every team
    opp_pfpg: Dict[int, float] = {}
    for tid, rec in pfpa.items():
        gp = rec["gp"] or 1
        opp_pfpg[tid] = rec["pf"] / gp

    sos: Dict[int, float] = defaultdict(float)
    counts: Dict[int, int] = defaultdict(int)
    for m in matches:
        a, b = m.home_team_id, m.away_team_id
        sos[a] += opp_pfpg.get(b, 0.0)
        counts[a] += 1
        sos[b] += opp_pfpg.get(a, 0.0)
        counts[b] += 1
    for tid in list(sos.keys()):
        c = counts.get(tid, 0)
        sos[tid] = sos[tid] / c if c > 0 else 0.0
    return sos


def _results_timeline(db: Session, league_id: int) -> Dict[int, List[str]]:
    out: Dict[int, List[str]] = defaultdict(list)
    for m in _scored_matches(db, league_id):
        hp = to_float(m.home_points)
        ap = to_float(m.away_points)
        if hp > ap:
            out[m.home_team_id].append("W")
            out[m.away_team_id].append("L")
        elif ap > hp:
            out[m.home_team_id].append("L")
            out[m.away_team_id].append("W")
        else:
            out[m.home_team_id].append("T")
            out[m.away_team_id].append("T")
    return out

def _streak_from(results: List[str]) -> str:
    """
    Compute current streak string like 'W3','L2','T1'. Empty => ''.
    """
    if not results:
        return ""
    last = results[-1]
    n = 0
    for r in reversed(results):
        if r == last:
            n += 1
        else:
            break
    return f"{last}{n}"


def _last5_from(results: List[str]) -> str:
    """
    Return 'W-L-T' counts for the last 5 (or fewer) results, e.g., '3-1-1'.
    """
    if not results:
        return "0-0-0"
    chunk = results[-5:]
    w = sum(1 for r in chunk if r == "W")
    l = sum(1 for r in chunk if r == "L")
    t = sum(1 for r in chunk if r == "T")
    return f"{w}-{l}-{t}"


@route.get("/{league_id}/power_rankings", operation_id="standings_power_rankings")

def power_rankings(league_id: int, db: Session = Depends(get_db)):
    """
    Power Rankings using Pythagorean expectation, augmented with:
      - sos: average opponents' PF per game they have scored so far
      - streak: current streak string, e.g., 'W3', 'L1', 'T1'
      - last5: record over the last five games, e.g., '3-2-0'

    Existing fields kept for backward compatibility:
      - team_id, team_name, pf, pa, pr
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = db.query(models.Team).filter(models.Team.league_id == league_id).all()
    name_by_id = {t.id: t.name for t in teams}

    pfpa_full = _pf_pa_by_team(db, league_id)
    sos_map = _sos_by_team(db, league_id)
    timelines = _results_timeline(db, league_id)

    rows = []
    for tid, tname in name_by_id.items():
        pf = float(pfpa_full.get(tid, {}).get("pf", 0.0))
        pa = float(pfpa_full.get(tid, {}).get("pa", 0.0))
        pr = _pythag_expectation(pf, pa, exponent=2.0)
        streak = _streak_from(timelines.get(tid, []))
        last5 = _last5_from(timelines.get(tid, []))
        sos = float(sos_map.get(tid, 0.0))
        rows.append({
            "team_id": tid,
            "team_name": tname,
            "pf": pf,
            "pa": pa,
            "pr": pr,
            "sos": sos,
            "streak": streak,
            "last5": last5,
        })

    rows.sort(key=lambda r: r["pr"], reverse=True)
    return rows
# --- League Insights -------------------------------------------------------------

@route.get("/{league_id}/insights", operation_id="standings_insights")

def standings_insights(league_id: int, db: Session = Depends(get_db)):
    """
    Read-only league insights that combine multiple analytics:
      - pr: Power Rankings rows + rank (desc by pr)
      - sos: Strength of schedule + rank (desc by sos)
      - streaks: current streak + last5 for each team
      - highs: best_week, worst_week from TeamScore; biggest_blowout from Matches

    Shape:
    {
      "ok": true,
      "league_id": int,
      "pr":    [{"team_id","team_name","pf","pa","pr","rank_pr"}, ...],
      "sos":   [{"team_id","team_name","sos","rank_sos"}, ...],
      "streaks":[{"team_id","team_name","streak","last5"}, ...],
      "highs": {
        "best_week": {"team_id","team_name","period","points"} | None,
        "worst_week":{"team_id","team_name","period","points"} | None,
        "biggest_blowout": {
          "match_id","week","home_team_id","away_team_id",
          "home_points","away_points","margin","winner_team_id"
        } | None
      }
    }
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # --- Base team map
    teams = db.query(models.Team).filter(models.Team.league_id == league_id).all()
    name_by_id = {t.id: t.name for t in teams}

    # --- Power Rankings rows + PR rank
    pfpa_full = _pf_pa_by_team(db, league_id)
    pr_rows = []
    for tid, tname in name_by_id.items():
        pf = float(pfpa_full.get(tid, {}).get("pf", 0.0))
        pa = float(pfpa_full.get(tid, {}).get("pa", 0.0))
        pr = _pythag_expectation(pf, pa, exponent=2.0)
        pr_rows.append({"team_id": tid, "team_name": tname, "pf": pf, "pa": pa, "pr": pr})
    pr_rows.sort(key=lambda r: r["pr"], reverse=True)
    for i, r in enumerate(pr_rows, start=1):
        r["rank_pr"] = i

    # --- SOS + rank
    sos_map = _sos_by_team(db, league_id)
    sos_rows = [{"team_id": tid, "team_name": name_by_id.get(tid, f"Team {tid}"), "sos": float(sos_map.get(tid, 0.0))}
                for tid in name_by_id.keys()]
    sos_rows.sort(key=lambda r: r["sos"], reverse=True)
    for i, r in enumerate(sos_rows, start=1):
        r["rank_sos"] = i

    # --- Streaks + last-5
    timelines = _results_timeline(db, league_id)
    streak_rows = []
    for tid, tname in name_by_id.items():
        res = timelines.get(tid, [])
        streak_rows.append({
            "team_id": tid,
            "team_name": tname,
            "streak": _streak_from(res),
            "last5": _last5_from(res),
        })

    # --- Highs: best / worst TeamScore weeks
    tscores = (
        db.query(models.TeamScore)
        .filter(models.TeamScore.league_id == league_id)
        .all()
    )

    best_week = None
    worst_week = None
    if tscores:
        best = max(tscores, key=lambda s: float(s.points or 0.0))
        worst = min(tscores, key=lambda s: float(s.points or 0.0))
        best_week = {
            "team_id": best.team_id,
            "team_name": name_by_id.get(best.team_id, f"Team {best.team_id}"),
            "period": best.period,
            "points": float(best.points or 0.0),
        }
        worst_week = {
            "team_id": worst.team_id,
            "team_name": name_by_id.get(worst.team_id, f"Team {worst.team_id}"),
            "period": worst.period,
            "points": float(worst.points or 0.0),
        }

    # --- Highs: biggest blowout from scored matches
    matches = _scored_matches(db, league_id)
    blow = None
    if matches:
        def _margin(m: models.Match) -> float:
            hp = float(m.home_points or 0.0)
            ap = float(m.away_points or 0.0)
            return abs(hp - ap)

        bm = max(matches, key=_margin)
        hp = float(bm.home_points or 0.0)
        ap = float(bm.away_points or 0.0)
        winner = bm.winner_team_id
        if winner is None:
            # tie: pick higher raw points as "winner" purely for display (stable, harmless)
            winner = bm.home_team_id if hp >= ap else bm.away_team_id

        blow = {
            "match_id": bm.id,
            "week": bm.week,
            "home_team_id": bm.home_team_id,
            "away_team_id": bm.away_team_id,
            "home_points": hp,
            "away_points": ap,
            "margin": abs(hp - ap),
            "winner_team_id": winner,
        }

    return {
        "ok": True,
        "league_id": league_id,
        "pr": pr_rows,
        "sos": sos_rows,
        "streaks": streak_rows,
        "highs": {
            "best_week": best_week,
            "worst_week": worst_week,
            "biggest_blowout": blow,
        },
    }
# --- Elo Rankings ---------------------------------------------------------------

@route.get("/{league_id}/elo", operation_id="standings_elo")

def elo_rankings(league_id: int, k: float = 32.0, db: Session = Depends(get_db)):
    """
    Compute Elo ratings from scored matches only (no persistence).
    - Start everyone at 1500.
    - Iterate scored matches in chronological order.
    - Update both teams after each game using classic Elo.
    Returns: [{team_id, team_name, elo, wins, losses, ties, gp}], sorted by elo desc.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    teams = db.query(models.Team).filter(models.Team.league_id == league_id).all()
    name_by_id = {t.id: t.name for t in teams}

    # Start ratings & simple records
    rating: Dict[int, float] = {tid: 1500.0 for tid in name_by_id.keys()}
    rec: Dict[int, Dict[str, int]] = {tid: {"wins": 0, "losses": 0, "ties": 0, "gp": 0} for tid in name_by_id.keys()}

    def expected(ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    matches = _scored_matches(db, league_id)  # defined above in this file
    for m in matches:
        a, b = m.home_team_id, m.away_team_id
        hp = float(m.home_points or 0.0)
        ap = float(m.away_points or 0.0)

        # Outcome as scores 1/0/0.5
        if hp > ap:
            Sa, Sb = 1.0, 0.0
            rec[a]["wins"] += 1; rec[b]["losses"] += 1
        elif ap > hp:
            Sa, Sb = 0.0, 1.0
            rec[b]["wins"] += 1; rec[a]["losses"] += 1
        else:
            Sa, Sb = 0.5, 0.5
            rec[a]["ties"] += 1; rec[b]["ties"] += 1

        rec[a]["gp"] += 1; rec[b]["gp"] += 1

        Ea = expected(rating[a], rating[b])
        Eb = expected(rating[b], rating[a])

        rating[a] = rating[a] + k * (Sa - Ea)
        rating[b] = rating[b] + k * (Sb - Eb)

    rows = []
    for tid, name in name_by_id.items():
        r = rec[tid]
        rows.append({
            "team_id": tid,
            "team_name": name,
            "elo": rating[tid],
            "wins": r["wins"],
            "losses": r["losses"],
            "ties": r["ties"],
            "gp": r["gp"],
        })

    rows.sort(key=lambda x: x["elo"], reverse=True)
    return rows
