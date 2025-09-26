# fantasy_stocks/schemas.py
from __future__ import annotations

from typing import Optional, Dict, List
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict


# -----------------------
# Shared / Enums
# -----------------------
class ScoringMode(str, Enum):
    PROJECTIONS = "PROJECTIONS"
    LIVE = "LIVE"


# -----------------------
# League
# -----------------------
class LeagueCreate(BaseModel):
    name: str
    roster_slots: int = 14
    starters: int = 8
    bucket_requirements: Optional[Dict[str, int]] = None
    # default to projections; router may ignore user roster settings but we allow passing mode
    scoring_mode: ScoringMode = ScoringMode.PROJECTIONS


class LeagueOut(BaseModel):
    id: int
    name: str
    roster_slots: int
    starters: int
    bucket_requirements: Optional[Dict[str, int]] = None
    scoring_mode: ScoringMode

    # Pydantic v2 replacement for Config(orm_mode=True)
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# Minimal view + mode update payloads (for GET /leagues/{id}, PATCH /leagues/{id}/mode)
class LeagueOutMinimal(BaseModel):
    id: int
    name: str
    scoring_mode: ScoringMode

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class LeagueModeUpdate(BaseModel):
    scoring_mode: ScoringMode


# -----------------------
# Team / Join League
# -----------------------
class JoinLeague(BaseModel):
    name: str
    owner: Optional[str] = None


class TeamOut(BaseModel):
    id: int
    name: str
    owner: Optional[str] = None
    league_id: int

    model_config = ConfigDict(from_attributes=True)


# -----------------------
# Draft
# -----------------------
class DraftPickIn(BaseModel):
    team_id: int
    symbol: str
    round: Optional[int] = None
    pick_no: Optional[int] = None


class DraftPickOut(BaseModel):
    id: int
    league_id: int
    team_id: int
    symbol: str
    round: int
    pick_no: int

    model_config = ConfigDict(from_attributes=True)


class RosterSlotOut(BaseModel):
    id: int
    team_id: int
    symbol: str
    is_active: bool
    bucket: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SetBucketIn(BaseModel):
    bucket: str


# -----------------------
# Lineup
# -----------------------
class SetLineupIn(BaseModel):
    team_id: int
    slot_ids: List[int]


class LineupOut(BaseModel):
    team_id: int
    starters: List[RosterSlotOut]
    bench: List[RosterSlotOut]


# -----------------------
# Schedule / Matches
# -----------------------
class GenerateScheduleIn(BaseModel):
    start_week: Optional[str] = None  # e.g., "2025-W39"


class MatchOut(BaseModel):
    id: int
    league_id: int
    week: str
    home_team_id: int
    away_team_id: int
    home_points: Optional[float] = None
    away_points: Optional[float] = None
    winner_team_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------
# Standings
# -----------------------
class ScoreOut(BaseModel):
    team_id: int
    team_name: str
    period: str
    points: float


class TableRow(BaseModel):
    team_id: int
    team_name: str
    wins: int
    losses: int
    ties: int
    games_played: int
    points_for: float
    points_against: float
    point_diff: float
    win_pct: float


# -----------------------
# Prices (live-data scaffolding)
# -----------------------
class PriceIn(BaseModel):
    symbol: str
    date: date
    open: Optional[float] = None
    close: Optional[float] = None


class PriceUpsertResult(BaseModel):
    inserted: int
    updated: int


# -----------------------
# (Optional) Users (kept minimal to satisfy imports)
# -----------------------
class UserCreate(BaseModel):
    name: str


class UserOut(BaseModel):
    id: int
    name: str


# (optional: keep this alias if other code still references UserIn)
UserIn = UserCreate
