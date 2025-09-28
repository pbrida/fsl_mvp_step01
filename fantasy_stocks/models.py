# fantasy_stocks/models.py
import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# -----------------------
# Scoring Mode
# -----------------------
class ScoringMode(str, enum.Enum):
    PROJECTIONS = "PROJECTIONS"
    LIVE = "LIVE"


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    # Draft/roster config
    roster_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=14)  # total picks per team
    starters: Mapped[int] = mapped_column(Integer, nullable=False, default=8)  # active lineup size

    # Required buckets that must sum to starters
    bucket_requirements: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)

    # NEW: scoring mode toggle (sim/projections vs. live price change scoring)
    scoring_mode: Mapped[ScoringMode] = mapped_column(
        SAEnum(ScoringMode), nullable=False, default=ScoringMode.PROJECTIONS
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    teams = relationship("Team", back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # <-- use .name (not team_name)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)

    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    league = relationship("League", back_populates="teams")

    roster_slots_rel = relationship("RosterSlot", back_populates="team", cascade="all, delete-orphan")
    picks = relationship("DraftPick", back_populates="team")

    __table_args__ = (UniqueConstraint("league_id", "name", name="uq_team_league_name"),)


class RosterSlot(Base):
    __tablename__ = "roster_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="roster_slots_rel")

    __table_args__ = (UniqueConstraint("team_id", "symbol", name="uq_team_symbol"),)


class DraftPick(Base):
    __tablename__ = "draft_picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pick_no: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="picks")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), index=True)

    # ISO week label like "2025-W39"
    week: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), index=True)

    # Filled when a week is closed
    home_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    winner_team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = tie

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TeamScore(Base):
    """
    Persistent per-week scoring snapshot for a team in a league.
    One row per (league_id, team_id, period) triplet.
    """

    __tablename__ = "team_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(10), index=True)  # ISO week label like "2025-W39"
    points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("league_id", "team_id", "period", name="uq_team_score_period"),)


# --- Player universe (securities) ---
class Security(Base):
    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_etf: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)

    primary_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # draft helpers
    adp: Mapped[float | None] = mapped_column(Float, nullable=True)  # lower is better
    proj_points: Mapped[float | None] = mapped_column(Float, nullable=True)  # higher is better

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# --- NEW: Daily Prices for LIVE scoring ---
class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    date: Mapped[datetime] = mapped_column(Date, index=True, nullable=False)  # store as date only
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_price_symbol_date"),)
