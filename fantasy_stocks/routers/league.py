from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

route = APIRouter(prefix="/leagues", tags=["leagues"])

# ---------------- Fixed Roster Rules (single source of truth) ----------------

BUCKET_LARGE_CAP = "LARGE_CAP"
BUCKET_MID_CAP = "MID_CAP"
BUCKET_SMALL_CAP = "SMALL_CAP"
BUCKET_ETF = "ETF"

PRIMARY_BUCKETS = [BUCKET_LARGE_CAP, BUCKET_MID_CAP, BUCKET_SMALL_CAP, BUCKET_ETF]
FLEX_ELIGIBILITY = PRIMARY_BUCKETS.copy()

FIXED_STARTER_SLOTS: dict[str, int] = {
    BUCKET_LARGE_CAP: 2,
    BUCKET_MID_CAP: 1,
    BUCKET_SMALL_CAP: 2,
    BUCKET_ETF: 1,
    "FLEX": 2,
}

FIXED_ROSTER_SIZE = 14
FIXED_STARTERS_TOTAL = 8
FIXED_BENCH_SIZE = FIXED_ROSTER_SIZE - FIXED_STARTERS_TOTAL


class RosterRules(BaseModel):
    starters: dict[str, int] = Field(
        ..., description="Exact starter slot counts by bucket (includes FLEX)."
    )
    roster_size: int = Field(14, description="Total roster size (starters + bench).")
    starters_total: int = Field(8, description="Total number of starters.")
    bench_size: int = Field(6, description="Total bench slots.")
    flex_eligibility: list[str] = Field(..., description="Which primary buckets can fill FLEX.")


def get_fixed_rules() -> RosterRules:
    return RosterRules(
        starters=FIXED_STARTER_SLOTS.copy(),
        roster_size=FIXED_ROSTER_SIZE,
        starters_total=FIXED_STARTERS_TOTAL,
        bench_size=FIXED_BENCH_SIZE,
        flex_eligibility=FLEX_ELIGIBILITY.copy(),
    )


# ---------------- routes ----------------


@route.get("/roster-rules", response_model=RosterRules)
def read_roster_rules():
    return get_fixed_rules()


@route.post("/", response_model=schemas.LeagueOut)
def create_league(body: schemas.LeagueCreate, db: Session = Depends(get_db)):
    existing = db.query(models.League).filter(models.League.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="League name already exists")

    rules = get_fixed_rules()

    league = models.League(
        name=body.name,
        roster_slots=rules.roster_size,
        starters=rules.starters_total,
        bucket_requirements=rules.starters,
        # allow caller to choose mode at creation; defaults to PROJECTIONS
        scoring_mode=models.ScoringMode(body.scoring_mode.value),
    )
    db.add(league)
    db.commit()
    db.refresh(league)
    return schemas.LeagueOut.model_validate(league)


@route.get("/", response_model=list[schemas.LeagueOut])
def list_leagues(db: Session = Depends(get_db)):
    leagues = db.query(models.League).order_by(models.League.id.asc()).all()
    return [schemas.LeagueOut.model_validate(l) for l in leagues]


@route.get("/{league_id}", response_model=schemas.LeagueOut)
def get_league(league_id: int, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return schemas.LeagueOut.model_validate(league)


@route.get("/{league_id}/teams", response_model=list[schemas.TeamOut])
def list_teams(league_id: int, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    teams = (
        db.query(models.Team)
        .filter(models.Team.league_id == league.id)
        .order_by(models.Team.id.asc())
        .all()
    )
    return [schemas.TeamOut.model_validate(t) for t in teams]


@route.post("/{league_id}/join", response_model=schemas.TeamOut)
def join_league(league_id: int, body: schemas.JoinLeague, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    dup = (
        db.query(models.Team)
        .filter(models.Team.league_id == league.id, models.Team.name == body.name.strip())
        .first()
    )
    if dup:
        raise HTTPException(
            status_code=400, detail="A team with that name already exists in this league"
        )

    team = models.Team(
        league_id=league.id,
        name=body.name.strip(),
        owner=(body.owner.strip() if body.owner else None),
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return schemas.TeamOut.model_validate(team)


# ---- settings (read-only for fixed rules) ----


class LeagueSettingsUpdate(BaseModel):
    roster_slots: int | None = None
    starters: int | None = None
    bucket_requirements: dict[str, int] | None = None  # ignored/blocked


@route.patch("/{league_id}/settings", response_model=schemas.LeagueOut)
def update_settings(league_id: int, body: LeagueSettingsUpdate, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    if (
        body.roster_slots is not None
        or body.starters is not None
        or body.bucket_requirements is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="League uses fixed roster rules; roster_slots, starters, and bucket_requirements are read-only.",
        )

    rules = get_fixed_rules()
    changed = False
    if league.roster_slots != rules.roster_size:
        league.roster_slots = rules.roster_size
        changed = True
    if league.starters != rules.starters_total:
        league.starters = rules.starters_total
        changed = True
    if league.bucket_requirements != rules.starters:
        league.bucket_requirements = rules.starters
        changed = True
    if changed:
        db.commit()
        db.refresh(league)

    return schemas.LeagueOut.model_validate(league)


# ---- scoring mode switch ----


class ModeUpdate(BaseModel):
    scoring_mode: schemas.ScoringMode


@route.patch("/{league_id}/mode", response_model=schemas.LeagueOut)
def update_mode(league_id: int, body: ModeUpdate, db: Session = Depends(get_db)):
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    # Convert schema enum to models enum explicitly to keep typing tools happy
    league.scoring_mode = models.ScoringMode(body.scoring_mode.value)
    db.add(league)
    db.commit()
    db.refresh(league)
    return schemas.LeagueOut.model_validate(league)
