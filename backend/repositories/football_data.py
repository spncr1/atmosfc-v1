"""Repository helpers for synced football data."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, or_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from backend.database.models import Competition, CompetitionSeason, Fixture, FixtureEvent, Season, SyncRun, Team

PROVIDER = "api_football"
FINISHED_STATUS_CODES = {"FT", "AET", "PEN"}


async def upsert_season(session: AsyncSession, year: int, *, is_current: bool = False) -> Season:
    season = await session.scalar(select(Season).where(Season.year == year))
    if season is None:
        season = Season(year=year, label=season_label(year), is_current=is_current)
        session.add(season)
    else:
        season.label = season_label(year)
        season.is_current = is_current
    await session.flush()
    return season


async def upsert_competition(session: AsyncSession, raw: dict[str, Any]) -> Competition:
    league = raw.get("league") or {}
    country = raw.get("country") or {}
    provider_id = int(league["id"])
    competition = await session.scalar(
        select(Competition).where(
            Competition.provider == PROVIDER,
            Competition.provider_competition_id == provider_id,
        )
    )
    values = {
        "provider": PROVIDER,
        "provider_competition_id": provider_id,
        "name": league.get("name") or f"Competition {provider_id}",
        "code": league.get("code"),
        "type": league.get("type"),
        "country_name": country.get("name"),
        "country_code": country.get("code"),
        "logo_url": league.get("logo"),
        "flag_url": country.get("flag"),
        "coverage": raw.get("coverage"),
        "raw_payload": raw,
        "is_active": True,
    }
    if competition is None:
        competition = Competition(**values)
        session.add(competition)
    else:
        _assign(competition, values)
    await session.flush()
    return competition


async def upsert_competition_season(
    session: AsyncSession,
    competition: Competition,
    season: Season,
    raw_season: dict[str, Any] | None,
) -> CompetitionSeason:
    competition_season = await session.scalar(
        select(CompetitionSeason).where(
            CompetitionSeason.competition_id == competition.id,
            CompetitionSeason.season_id == season.id,
        )
    )
    raw = raw_season or {}
    values = {
        "competition_id": competition.id,
        "season_id": season.id,
        "start_date": parse_date(raw.get("start")),
        "end_date": parse_date(raw.get("end")),
        "is_current": bool(raw.get("current")),
        "coverage": raw.get("coverage"),
        "raw_payload": raw or None,
    }
    if competition_season is None:
        competition_season = CompetitionSeason(**values)
        session.add(competition_season)
    else:
        _assign(competition_season, values)
    await session.flush()
    return competition_season


async def upsert_team(session: AsyncSession, raw: dict[str, Any]) -> Team:
    team_data = raw.get("team") or raw
    venue = raw.get("venue") or {}
    provider_id = int(team_data["id"])
    team = await session.scalar(
        select(Team).where(
            Team.provider == PROVIDER,
            Team.provider_team_id == provider_id,
        )
    )
    values = {
        "provider": PROVIDER,
        "provider_team_id": provider_id,
        "name": team_data.get("name") or f"Team {provider_id}",
        "code": team_data.get("code"),
        "country_name": team_data.get("country"),
        "founded": safe_int(team_data.get("founded")),
        "is_national": bool(team_data.get("national")),
        "logo_url": team_data.get("logo"),
        "venue_name": venue.get("name"),
        "venue_city": venue.get("city"),
        "venue_image_url": venue.get("image"),
        "raw_payload": raw,
    }
    if team is None:
        team = Team(**values)
        session.add(team)
    else:
        _assign(team, values)
    await session.flush()
    return team


async def upsert_teams(session: AsyncSession, rows: list[dict[str, Any]]) -> dict[int, Team]:
    provider_ids = [int((row.get("team") or row)["id"]) for row in rows]
    existing = await teams_by_provider_ids(session, provider_ids)
    teams: dict[int, Team] = {}
    for raw in rows:
        team_data = raw.get("team") or raw
        provider_id = int(team_data["id"])
        values = team_values(raw)
        team = existing.get(provider_id)
        if team is None:
            team = Team(**values)
            session.add(team)
        else:
            _assign(team, values)
        teams[provider_id] = team
    await session.flush()
    return teams


async def upsert_fixture(
    session: AsyncSession,
    raw: dict[str, Any],
    competition: Competition,
    season: Season,
    home_team: Team,
    away_team: Team,
) -> Fixture:
    fixture_data = raw.get("fixture") or {}
    provider_id = int(fixture_data["id"])
    status = fixture_data.get("status") or {}
    venue = fixture_data.get("venue") or {}
    goals = raw.get("goals") or {}
    score = raw.get("score") or {}
    halftime = score.get("halftime") or {}
    fulltime = score.get("fulltime") or {}
    extratime = score.get("extratime") or {}
    penalty = score.get("penalty") or {}
    fixture = await session.scalar(
        select(Fixture).where(
            Fixture.provider == PROVIDER,
            Fixture.provider_fixture_id == provider_id,
        )
    )
    values = {
        "provider": PROVIDER,
        "provider_fixture_id": provider_id,
        "competition_id": competition.id,
        "season_id": season.id,
        "home_team_id": home_team.id,
        "away_team_id": away_team.id,
        "kickoff_at": parse_datetime(fixture_data.get("date")),
        "status_short": status.get("short"),
        "status_long": status.get("long"),
        "elapsed": safe_int(status.get("elapsed")),
        "round_name": (raw.get("league") or {}).get("round"),
        "venue_name": venue.get("name"),
        "venue_city": venue.get("city"),
        "home_goals": safe_int(goals.get("home")),
        "away_goals": safe_int(goals.get("away")),
        "halftime_home_goals": safe_int(halftime.get("home")),
        "halftime_away_goals": safe_int(halftime.get("away")),
        "fulltime_home_goals": safe_int(fulltime.get("home")),
        "fulltime_away_goals": safe_int(fulltime.get("away")),
        "extratime_home_goals": safe_int(extratime.get("home")),
        "extratime_away_goals": safe_int(extratime.get("away")),
        "penalty_home_goals": safe_int(penalty.get("home")),
        "penalty_away_goals": safe_int(penalty.get("away")),
        "raw_payload": raw,
    }
    if fixture is None:
        fixture = Fixture(**values)
        session.add(fixture)
    else:
        _assign(fixture, values)
    await session.flush()
    return fixture


async def replace_fixture_events(
    session: AsyncSession,
    fixture: Fixture,
    raw_events: list[dict[str, Any]],
) -> int:
    await session.execute(delete(FixtureEvent).where(FixtureEvent.fixture_id == fixture.id))
    for raw in raw_events:
        team_data = raw.get("team") or {}
        player = raw.get("player") or {}
        assist = raw.get("assist") or {}
        time_data = raw.get("time") or {}
        team = await team_by_provider_id(session, safe_int(team_data.get("id")))
        session.add(
            FixtureEvent(
                fixture_id=fixture.id,
                team_id=team.id if team else None,
                provider_player_id=safe_int(player.get("id")),
                player_name=player.get("name"),
                provider_assist_player_id=safe_int(assist.get("id")),
                assist_player_name=assist.get("name"),
                minute=safe_int(time_data.get("elapsed")),
                extra_minute=safe_int(time_data.get("extra")),
                type=raw.get("type") or "Unknown",
                detail=raw.get("detail"),
                comments=raw.get("comments"),
                raw_payload=raw,
            )
        )
    await session.flush()
    return len(raw_events)


async def team_by_provider_id(session: AsyncSession, provider_team_id: int | None) -> Team | None:
    if provider_team_id is None:
        return None
    return await session.scalar(
        select(Team).where(
            Team.provider == PROVIDER,
            Team.provider_team_id == provider_team_id,
        )
    )


async def teams_by_provider_ids(session: AsyncSession, provider_team_ids: list[int]) -> dict[int, Team]:
    if not provider_team_ids:
        return {}
    rows = await session.scalars(
        select(Team).where(
            Team.provider == PROVIDER,
            Team.provider_team_id.in_(set(provider_team_ids)),
        )
    )
    return {team.provider_team_id: team for team in rows}


async def competition_by_provider_id(session: AsyncSession, provider_competition_id: int) -> Competition | None:
    return await session.scalar(
        select(Competition).where(
            Competition.provider == PROVIDER,
            Competition.provider_competition_id == provider_competition_id,
        )
    )


async def recent_fixtures(
    session: AsyncSession,
    *,
    limit: int,
    provider_competition_id: int | None = None,
) -> list[Fixture]:
    query = (
        select(Fixture)
        .options(
            joinedload(Fixture.competition),
            joinedload(Fixture.season),
            joinedload(Fixture.home_team),
            joinedload(Fixture.away_team),
        )
        .join(Competition, Competition.id == Fixture.competition_id)
        .where(
            Fixture.provider == PROVIDER,
            Fixture.status_short.in_(FINISHED_STATUS_CODES),
        )
        .order_by(Fixture.kickoff_at.desc())
        .limit(limit)
    )
    if provider_competition_id is not None:
        query = query.where(Competition.provider_competition_id == provider_competition_id)
    rows = await session.scalars(query)
    return list(rows)


async def search_fixtures(
    session: AsyncSession,
    *,
    query_text: str = "",
    provider_competition_id: int | None = None,
    season_year: int | None = None,
) -> list[Fixture]:
    home_team = aliased(Team)
    away_team = aliased(Team)
    query = (
        select(Fixture)
        .options(
            joinedload(Fixture.competition),
            joinedload(Fixture.season),
            joinedload(Fixture.home_team),
            joinedload(Fixture.away_team),
        )
        .join(Competition, Competition.id == Fixture.competition_id)
        .join(Season, Season.id == Fixture.season_id)
        .join(home_team, home_team.id == Fixture.home_team_id)
        .join(away_team, away_team.id == Fixture.away_team_id)
        .where(
            Fixture.provider == PROVIDER,
            Fixture.status_short.in_(FINISHED_STATUS_CODES),
        )
        .order_by(Fixture.kickoff_at.desc())
    )
    if provider_competition_id is not None:
        query = query.where(Competition.provider_competition_id == provider_competition_id)
    if season_year is not None:
        query = query.where(Season.year == season_year)
    clean_query = " ".join(query_text.split())
    if clean_query:
        pattern = f"%{clean_query}%"
        query = query.where(
            or_(
                home_team.name.ilike(pattern),
                away_team.name.ilike(pattern),
                Competition.name.ilike(pattern),
                Fixture.round_name.ilike(pattern),
            )
        )
    rows = await session.scalars(query)
    return list(rows)


async def synced_competitions(session: AsyncSession) -> list[Competition]:
    rows = await session.scalars(
        select(Competition).where(
            Competition.provider == PROVIDER,
            Competition.is_active.is_(True),
        )
    )
    return list(rows)


async def synced_competition_seasons(session: AsyncSession) -> list[Season]:
    rows = await session.scalars(
        select(Season)
        .join(CompetitionSeason, CompetitionSeason.season_id == Season.id)
        .join(Competition, Competition.id == CompetitionSeason.competition_id)
        .where(
            Competition.provider == PROVIDER,
            Competition.is_active.is_(True),
        )
        .distinct()
        .order_by(Season.year.desc())
    )
    return list(rows)


async def create_sync_run(
    session: AsyncSession,
    sync_type: str,
    *,
    season_year: int | None = None,
    provider_competition_id: int | None = None,
    sync_metadata: dict[str, Any] | None = None,
) -> SyncRun:
    sync_run = SyncRun(
        provider=PROVIDER,
        sync_type=sync_type,
        status="running",
        season_year=season_year,
        provider_competition_id=provider_competition_id,
        sync_metadata=sync_metadata,
    )
    session.add(sync_run)
    await session.flush()
    return sync_run


async def mark_running_syncs_failed(session: AsyncSession, sync_type: str, message: str) -> None:
    await session.execute(
        update(SyncRun)
        .where(SyncRun.provider == PROVIDER, SyncRun.sync_type == sync_type, SyncRun.status == "running")
        .values(status="failed", finished_at=datetime.now(timezone.utc), error_message=message)
    )
    await session.flush()


async def finish_sync_run(
    session: AsyncSession,
    sync_run: SyncRun,
    *,
    status: str,
    records_seen: int = 0,
    records_changed: int = 0,
    error_message: str | None = None,
) -> None:
    sync_run.status = status
    sync_run.finished_at = datetime.now(timezone.utc)
    sync_run.records_seen = records_seen
    sync_run.records_changed = records_changed
    sync_run.error_message = error_message
    await session.flush()


async def table_counts(session: AsyncSession) -> dict[str, int]:
    tables = {
        "competitions": Competition,
        "seasons": Season,
        "competition_seasons": CompetitionSeason,
        "teams": Team,
        "fixtures": Fixture,
        "fixture_events": FixtureEvent,
        "sync_runs": SyncRun,
    }
    counts: dict[str, int] = {}
    for name, model in tables.items():
        counts[name] = int(await session.scalar(select(func.count()).select_from(model)) or 0)
    return counts


def season_label(year: int) -> str:
    return f"{year}/{str(year + 1)[-2:]}"


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    clean = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def team_values(raw: dict[str, Any]) -> dict[str, Any]:
    team_data = raw.get("team") or raw
    venue = raw.get("venue") or {}
    provider_id = int(team_data["id"])
    return {
        "provider": PROVIDER,
        "provider_team_id": provider_id,
        "name": team_data.get("name") or f"Team {provider_id}",
        "code": team_data.get("code"),
        "country_name": team_data.get("country"),
        "founded": safe_int(team_data.get("founded")),
        "is_national": bool(team_data.get("national")),
        "logo_url": team_data.get("logo"),
        "venue_name": venue.get("name"),
        "venue_city": venue.get("city"),
        "venue_image_url": venue.get("image"),
        "raw_payload": raw,
    }


def _assign(model: Any, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(model, key, value)
