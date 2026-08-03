"""Sync API-Football data into the local database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_sessionmaker
from backend.database.models import Competition, Fixture, Season, Team
from backend.providers.api_football import ApiFootballClient
from backend.repositories import football_data as repo


@dataclass(frozen=True)
class CompetitionTarget:
    provider_id: int
    label: str


CORE_COMPETITIONS = [
    CompetitionTarget(39, "Premier League"),
    CompetitionTarget(140, "La Liga"),
    CompetitionTarget(78, "Bundesliga"),
    CompetitionTarget(135, "Serie A"),
    CompetitionTarget(61, "Ligue 1"),
    CompetitionTarget(2, "UEFA Champions League"),
    CompetitionTarget(3, "UEFA Europa League"),
    CompetitionTarget(848, "UEFA Conference League"),
]


async def sync_core_football_data(
    *,
    season_years: list[int] | None = None,
    recent_limit: int = 3,
    include_events: bool = True,
) -> dict[str, Any]:
    """Sync the first production MVP slice from API-Football into Postgres."""

    client = ApiFootballClient()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await repo.mark_running_syncs_failed(session, "api_football_core", "Superseded by a new sync run.")
        sync_run = await repo.create_sync_run(
            session,
            "api_football_core",
            sync_metadata={
                "requested_seasons": season_years,
                "recent_limit": recent_limit,
                "include_events": include_events,
            },
        )
        await session.commit()
        try:
            result = await _sync_core(session, client, season_years, recent_limit, include_events)
        except Exception as exc:
            await repo.finish_sync_run(session, sync_run, status="failed", error_message=str(exc))
            await session.commit()
            raise

        await repo.finish_sync_run(
            session,
            sync_run,
            status="succeeded",
            records_seen=result["records_seen"],
            records_changed=result["records_changed"],
        )
        result["table_counts"] = await repo.table_counts(session)
        await session.commit()
        return result


async def _sync_core(
    session: AsyncSession,
    client: ApiFootballClient,
    season_years: list[int] | None,
    recent_limit: int,
    include_events: bool,
) -> dict[str, Any]:
    api_seasons = await client.seasons()
    selected_seasons = select_sync_seasons(api_seasons, season_years)
    records_seen = len(api_seasons)
    records_changed = 0
    synced = {
        "api_seasons": len(api_seasons),
        "selected_seasons": selected_seasons,
        "competitions": 0,
        "competition_seasons": 0,
        "teams": 0,
        "fixtures": 0,
        "fixture_events": 0,
        "event_requests": 0,
    }

    current_year = current_european_season_year()
    for season_year in api_seasons:
        await repo.upsert_season(session, season_year, is_current=season_year == current_year)
        records_changed += 1

    for target in CORE_COMPETITIONS:
        for season_year in selected_seasons:
            league_rows = await client.leagues(league_id=target.provider_id, season=season_year)
            records_seen += len(league_rows)
            if not league_rows:
                continue

            competition = await repo.upsert_competition(session, league_rows[0])
            season = await repo.upsert_season(session, season_year, is_current=season_year == current_year)
            synced["competitions"] += 1
            records_changed += 2

            raw_season = league_season_payload(league_rows[0], season_year)
            await repo.upsert_competition_season(session, competition, season, raw_season)
            synced["competition_seasons"] += 1
            records_changed += 1

            team_rows = await client.teams(league_id=target.provider_id, season=season_year)
            records_seen += len(team_rows)
            teams_by_provider_id = await repo.upsert_teams(session, team_rows)
            records_changed += len(team_rows)
            synced["teams"] += len(team_rows)

            fixtures = await client.fixtures(
                league_id=target.provider_id,
                season=season_year,
                status="FT-AET-PEN",
                last=max(1, recent_limit),
            )
            records_seen += len(fixtures)
            for raw_fixture in fixtures:
                fixture, new_teams = await sync_fixture(session, raw_fixture, competition, season, teams_by_provider_id)
                synced["fixtures"] += 1
                synced["teams"] += new_teams
                records_changed += 1 + new_teams

                if include_events:
                    events = await client.fixture_events(fixture.provider_fixture_id)
                    synced["event_requests"] += 1
                    synced["fixture_events"] += await repo.replace_fixture_events(session, fixture, events)
                    records_seen += len(events)
                    records_changed += len(events)

    return {
        "records_seen": records_seen,
        "records_changed": records_changed,
        "synced": synced,
    }


async def sync_fixture(
    session: AsyncSession,
    raw_fixture: dict[str, Any],
    competition: Competition,
    season: Season,
    teams_by_provider_id: dict[int, Team],
) -> tuple[Fixture, int]:
    teams = raw_fixture.get("teams") or {}
    home_raw = teams.get("home") or {}
    away_raw = teams.get("away") or {}
    new_teams = 0

    home_team = teams_by_provider_id.get(int(home_raw["id"]))
    if home_team is None:
        home_team = await repo.upsert_team(session, {"team": home_raw})
        teams_by_provider_id[home_team.provider_team_id] = home_team
        new_teams += 1

    away_team = teams_by_provider_id.get(int(away_raw["id"]))
    if away_team is None:
        away_team = await repo.upsert_team(session, {"team": away_raw})
        teams_by_provider_id[away_team.provider_team_id] = away_team
        new_teams += 1

    fixture = await repo.upsert_fixture(session, raw_fixture, competition, season, home_team, away_team)
    return fixture, new_teams


def select_sync_seasons(api_seasons: list[int], requested: list[int] | None) -> list[int]:
    available = sorted(set(api_seasons))
    if not available:
        return []
    if requested:
        return [season for season in requested if season in available]

    current = current_european_season_year()
    selected = [season for season in (current, current - 1) if season in available]
    return selected or [available[-1]]


def current_european_season_year(today: date | None = None) -> int:
    value = today or date.today()
    return value.year if value.month >= 7 else value.year - 1


def league_season_payload(raw_league: dict[str, Any], season_year: int) -> dict[str, Any] | None:
    for item in raw_league.get("seasons", []) or []:
        if item.get("year") == season_year:
            return item
    return None
