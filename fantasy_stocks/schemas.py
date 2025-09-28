# fantasy_stocks/schemas.py
from __future__ import annotations

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
    bucket_requirements: dict[str, int] | None = None
    # default to projections; router may ignore user roster settings but we allow passing mode
    scoring_mode: ScoringMode = ScoringMode.PROJECTIONS


class LeagueOut(BaseModel):
    id: int
    name: str
    roster_slots: int
    starters: int
    bucket_requirements: dict[str, int] | None = None
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
    owner: str | None = None


class TeamOut(BaseModel):
    id: int
    name: str
    owner: str | None = None
    league_id: int

    model_config = ConfigDict(from_attributes=True)


# -----------------------
# Draft
# -----------------------
class DraftPickIn(BaseModel):
    team_id: int
    symbol: str
    round: int | None = None
    pick_no: int | None = None


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
    bucket: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SetBucketIn(BaseModel):
    bucket: str


# -----------------------
# Lineup
# -----------------------
class SetLineupIn(BaseModel):
    team_id: int
    slot_ids: list[int]


class LineupOut(BaseModel):
    team_id: int
    starters: list[RosterSlotOut]
    bench: list[RosterSlotOut]


# -----------------------
# Schedule / Matches
# -----------------------
class GenerateScheduleIn(BaseModel):
    start_week: str | None = None  # e.g., "2025-W39"


class MatchOut(BaseModel):
    id: int
    league_id: int
    week: str
    home_team_id: int
    away_team_id: int
    home_points: float | None = None
    away_points: float | None = None
    winner_team_id: int | None = None

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
    open: float | None = None
    close: float | None = None


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
