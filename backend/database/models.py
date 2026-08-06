"""SQLAlchemy models for locally stored football data."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Competition(Base, TimestampMixin):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="api_football")
    provider_competition_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    flag_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    seasons: Mapped[list[CompetitionSeason]] = relationship(back_populates="competition", cascade="all, delete-orphan")
    fixtures: Mapped[list[Fixture]] = relationship(back_populates="competition")

    __table_args__ = (
        UniqueConstraint("provider", "provider_competition_id", name="uq_competitions_provider_id"),
        Index("ix_competitions_name", "name"),
    )


class Season(Base, TimestampMixin):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    competitions: Mapped[list[CompetitionSeason]] = relationship(back_populates="season", cascade="all, delete-orphan")
    fixtures: Mapped[list[Fixture]] = relationship(back_populates="season")


class CompetitionSeason(Base, TimestampMixin):
    __tablename__ = "competition_seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    competition: Mapped[Competition] = relationship(back_populates="seasons")
    season: Mapped[Season] = relationship(back_populates="competitions")

    __table_args__ = (
        UniqueConstraint("competition_id", "season_id", name="uq_competition_seasons_competition_season"),
    )


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="api_football")
    provider_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str | None] = mapped_column(String(24), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    founded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_national: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    venue_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    profile_enrichment: Mapped[TeamProfileEnrichment | None] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
        uselist=False,
    )
    home_fixtures: Mapped[list[Fixture]] = relationship(back_populates="home_team", foreign_keys="Fixture.home_team_id")
    away_fixtures: Mapped[list[Fixture]] = relationship(back_populates="away_team", foreign_keys="Fixture.away_team_id")

    __table_args__ = (
        UniqueConstraint("provider", "provider_team_id", name="uq_teams_provider_id"),
        Index("ix_teams_name", "name"),
    )


class TeamProfileEnrichment(Base, TimestampMixin):
    __tablename__ = "team_profile_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="api_football")
    provider_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    wikidata_qid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wikipedia_title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    wikipedia_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    facts_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attribution_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    team: Mapped[Team] = relationship(back_populates="profile_enrichment")

    __table_args__ = (
        UniqueConstraint("team_id", name="uq_team_profile_enrichments_team"),
        UniqueConstraint("provider", "provider_team_id", name="uq_team_profile_enrichments_provider_team"),
        Index("ix_team_profile_enrichments_wikidata_qid", "wikidata_qid"),
        Index("ix_team_profile_enrichments_needs_review", "needs_review"),
    )


class Fixture(Base, TimestampMixin):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="api_football")
    provider_fixture_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status_short: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_long: Mapped[str | None] = mapped_column(String(80), nullable=True)
    elapsed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    round_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    halftime_home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    halftime_away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fulltime_home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fulltime_away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extratime_home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extratime_away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    penalty_home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    penalty_away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    competition: Mapped[Competition] = relationship(back_populates="fixtures")
    season: Mapped[Season] = relationship(back_populates="fixtures")
    home_team: Mapped[Team] = relationship(back_populates="home_fixtures", foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(back_populates="away_fixtures", foreign_keys=[away_team_id])
    events: Mapped[list[FixtureEvent]] = relationship(back_populates="fixture", cascade="all, delete-orphan")
    event_sync_status: Mapped[FixtureEventSyncStatus | None] = relationship(
        back_populates="fixture",
        cascade="all, delete-orphan",
        uselist=False,
    )
    youtube_comment_cache: Mapped[YouTubeCommentCache | None] = relationship(
        back_populates="fixture",
        cascade="all, delete-orphan",
        uselist=False,
    )
    analysis_cache: Mapped[AnalysisCache | None] = relationship(
        back_populates="fixture",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_fixture_id", name="uq_fixtures_provider_id"),
        Index("ix_fixtures_kickoff_at", "kickoff_at"),
        Index("ix_fixtures_competition_season", "competition_id", "season_id"),
        Index("ix_fixtures_teams", "home_team_id", "away_team_id"),
    )


class FixtureEvent(Base, TimestampMixin):
    __tablename__ = "fixture_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    provider_player_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_assist_player_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assist_player_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(120), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="events")
    team: Mapped[Team | None] = relationship()

    __table_args__ = (
        Index("ix_fixture_events_fixture_minute", "fixture_id", "minute"),
        Index("ix_fixture_events_type", "type"),
    )


class FixtureEventSyncStatus(Base, TimestampMixin):
    __tablename__ = "fixture_event_sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="event_sync_status")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_event_sync_status_fixture"),
        Index("ix_fixture_event_sync_status_status", "status"),
        Index("ix_fixture_event_sync_status_checked_at", "checked_at"),
    )


class YouTubeCommentCache(Base, TimestampMixin):
    __tablename__ = "youtube_comment_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    raw_comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysed_comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_video_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_video_channel: Mapped[str | None] = mapped_column(String(160), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="youtube_comment_cache")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_youtube_comment_cache_fixture"),
        Index("ix_youtube_comment_cache_status", "status"),
        Index("ix_youtube_comment_cache_checked_at", "checked_at"),
    )


class AnalysisCache(Base, TimestampMixin):
    __tablename__ = "analysis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="complete")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="analysis_cache")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_analysis_cache_fixture"),
        Index("ix_analysis_cache_status", "status"),
        Index("ix_analysis_cache_checked_at", "checked_at"),
    )


class BackgroundJob(Base, TimestampMixin):
    __tablename__ = "background_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    job_key: Mapped[str] = mapped_column(String(260), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("job_type", "job_key", name="uq_background_jobs_type_key"),
        Index("ix_background_jobs_status_available", "status", "available_at"),
        Index("ix_background_jobs_type_status", "job_type", "status"),
    )


class SyncRun(Base, TimestampMixin):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="api_football")
    sync_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    season_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_competition_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_fixture_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_sync_runs_type_status", "sync_type", "status"),
        Index("ix_sync_runs_started_at", "started_at"),
    )


class ArchiveSyncStatus(Base, TimestampMixin):
    __tablename__ = "archive_sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="api_football")
    scope_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(260), nullable=False)
    provider_team_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    provider_competition_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "scope_key", name="uq_archive_sync_status_provider_scope_key"),
        Index("ix_archive_sync_status_scope_status", "scope_type", "status"),
        Index("ix_archive_sync_status_lookup", "provider_competition_id", "season_year"),
    )
