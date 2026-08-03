"""Create initial football data schema.

Revision ID: 20260803_0001
Revises:
Create Date: 2026-08-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260803_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_competition_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=True),
        sa.Column("country_name", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=12), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("flag_url", sa.Text(), nullable=True),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_competition_id", name="uq_competitions_provider_id"),
    )
    op.create_index("ix_competitions_name", "competitions", ["name"])

    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=True),
        sa.Column("country_name", sa.String(length=120), nullable=True),
        sa.Column("founded", sa.Integer(), nullable=True),
        sa.Column("is_national", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("venue_name", sa.String(length=160), nullable=True),
        sa.Column("venue_city", sa.String(length=120), nullable=True),
        sa.Column("venue_image_url", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_team_id", name="uq_teams_provider_id"),
    )
    op.create_index("ix_teams_name", "teams", ["name"])

    op.create_table(
        "competition_seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competition_id", "season_id", name="uq_competition_seasons_competition_season"),
    )

    op.create_table(
        "fixtures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_fixture_id", sa.BigInteger(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_short", sa.String(length=16), nullable=True),
        sa.Column("status_long", sa.String(length=80), nullable=True),
        sa.Column("elapsed", sa.Integer(), nullable=True),
        sa.Column("round_name", sa.String(length=160), nullable=True),
        sa.Column("venue_name", sa.String(length=160), nullable=True),
        sa.Column("venue_city", sa.String(length=120), nullable=True),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.Column("halftime_home_goals", sa.Integer(), nullable=True),
        sa.Column("halftime_away_goals", sa.Integer(), nullable=True),
        sa.Column("fulltime_home_goals", sa.Integer(), nullable=True),
        sa.Column("fulltime_away_goals", sa.Integer(), nullable=True),
        sa.Column("extratime_home_goals", sa.Integer(), nullable=True),
        sa.Column("extratime_away_goals", sa.Integer(), nullable=True),
        sa.Column("penalty_home_goals", sa.Integer(), nullable=True),
        sa.Column("penalty_away_goals", sa.Integer(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_fixture_id", name="uq_fixtures_provider_id"),
    )
    op.create_index("ix_fixtures_competition_season", "fixtures", ["competition_id", "season_id"])
    op.create_index("ix_fixtures_kickoff_at", "fixtures", ["kickoff_at"])
    op.create_index("ix_fixtures_teams", "fixtures", ["home_team_id", "away_team_id"])

    op.create_table(
        "fixture_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("provider_player_id", sa.Integer(), nullable=True),
        sa.Column("player_name", sa.String(length=160), nullable=True),
        sa.Column("provider_assist_player_id", sa.Integer(), nullable=True),
        sa.Column("assist_player_name", sa.String(length=160), nullable=True),
        sa.Column("minute", sa.Integer(), nullable=True),
        sa.Column("extra_minute", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.String(length=120), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fixture_id"], ["fixtures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fixture_events_fixture_minute", "fixture_events", ["fixture_id", "minute"])
    op.create_index("ix_fixture_events_type", "fixture_events", ["type"])

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("sync_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("provider_competition_id", sa.Integer(), nullable=True),
        sa.Column("provider_fixture_id", sa.BigInteger(), nullable=True),
        sa.Column("records_seen", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_changed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_started_at", "sync_runs", ["started_at"])
    op.create_index("ix_sync_runs_type_status", "sync_runs", ["sync_type", "status"])


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_table("fixture_events")
    op.drop_table("fixtures")
    op.drop_table("competition_seasons")
    op.drop_table("teams")
    op.drop_table("seasons")
    op.drop_table("competitions")
