"""baseline schema

Revision ID: 2e9654d2ca0d
Revises:
Create Date: 2025-09-23 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2e9654d2ca0d"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # leagues
    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column(
            "roster_slots", sa.Integer(), nullable=False, server_default=sa.text("14")
        ),
        sa.Column(
            "starters", sa.Integer(), nullable=False, server_default=sa.text("8")
        ),
        sa.Column("bucket_requirements", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_leagues_name", "leagues", ["name"], unique=True)

    # teams
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column(
            "league_id",
            sa.Integer(),
            sa.ForeignKey("leagues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "league_id", "name", name="uq_team_league_name"
        ),  # <— inline UNIQUE (SQLite-safe)
    )
    op.create_index("ix_teams_league_id", "teams", ["league_id"])

    # roster_slots
    op.create_table(
        "roster_slots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("bucket", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "team_id", "symbol", name="uq_team_symbol"
        ),  # <— inline UNIQUE (SQLite-safe)
    )
    op.create_index("ix_roster_slots_team_id", "roster_slots", ["team_id"])

    # draft_picks
    op.create_table(
        "draft_picks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "league_id",
            sa.Integer(),
            sa.ForeignKey("leagues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("pick_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_draft_picks_league_id", "draft_picks", ["league_id"])
    op.create_index("ix_draft_picks_team_id", "draft_picks", ["team_id"])

    # matches
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "league_id",
            sa.Integer(),
            sa.ForeignKey("leagues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week", sa.String(length=10), nullable=False),
        sa.Column(
            "home_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "away_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("home_points", sa.Float(), nullable=True),
        sa.Column("away_points", sa.Float(), nullable=True),
        sa.Column("winner_team_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_matches_league_id", "matches", ["league_id"])
    op.create_index("ix_matches_week", "matches", ["week"])
    op.create_index("ix_matches_home_team_id", "matches", ["home_team_id"])
    op.create_index("ix_matches_away_team_id", "matches", ["away_team_id"])

    # team_scores
    op.create_table(
        "team_scores",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "league_id",
            sa.Integer(),
            sa.ForeignKey("leagues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("points", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "league_id", "team_id", "period", name="uq_team_score_period"
        ),  # inline UNIQUE
    )
    op.create_index("ix_team_scores_league_id", "team_scores", ["league_id"])
    op.create_index("ix_team_scores_team_id", "team_scores", ["team_id"])
    op.create_index("ix_team_scores_period", "team_scores", ["period"])


def downgrade() -> None:
    # drop in reverse dependency order
    op.drop_index("ix_team_scores_period", table_name="team_scores")
    op.drop_index("ix_team_scores_team_id", table_name="team_scores")
    op.drop_index("ix_team_scores_league_id", table_name="team_scores")
    op.drop_table("team_scores")

    op.drop_index("ix_matches_away_team_id", table_name="matches")
    op.drop_index("ix_matches_home_team_id", table_name="matches")
    op.drop_index("ix_matches_week", table_name="matches")
    op.drop_index("ix_matches_league_id", table_name="matches")
    op.drop_table("matches")

    op.drop_index("ix_draft_picks_team_id", table_name="draft_picks")
    op.drop_index("ix_draft_picks_league_id", table_name="draft_picks")
    op.drop_table("draft_picks")

    op.drop_index("ix_roster_slots_team_id", table_name="roster_slots")
    op.drop_table("roster_slots")

    op.drop_index("ix_teams_league_id", table_name="teams")
    op.drop_table("teams")

    op.drop_index("ix_leagues_name", table_name="leagues")
    op.drop_table("leagues")
