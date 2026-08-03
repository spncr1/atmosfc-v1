"""App-level match reads backed by the local database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from backend.database.models import Competition, Fixture, FixtureEvent, Team
from backend.database.session import get_sessionmaker
from backend.models.schemas import MatchEvent, MatchSummary
from backend.repositories import football_data as repo


class MatchDataError(RuntimeError):
    """Raised when locally stored match data cannot satisfy a request."""


COMPETITION_CODE_TO_PROVIDER_ID = {
    "PL": 39,
    "PD": 140,
    "BL1": 78,
    "SA": 135,
    "FL1": 61,
    "CL": 2,
    "EL": 3,
    "UECL": 848,
    "UCL": 848,
}

PROVIDER_ID_TO_COMPETITION_CODE = {
    provider_id: code
    for code, provider_id in COMPETITION_CODE_TO_PROVIDER_ID.items()
    if code != "UCL"
}
APP_COMPETITION_NAMES = {
    39: "Premier League",
    140: "La Liga",
    78: "Bundesliga",
    135: "Serie A",
    61: "Ligue 1",
    2: "UEFA Champions League",
    3: "UEFA Europa League",
    848: "UEFA Conference League",
}


async def recent_matches(limit: int = 18, competition: str | None = None) -> list[MatchSummary]:
    """Return recent finished matches from locally synced API-Football data."""

    provider_competition_id = provider_competition_id_for_code(competition)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            fixtures = await repo.recent_fixtures(
                session,
                limit=limit,
                provider_competition_id=provider_competition_id,
            )
    except SQLAlchemyError as exc:
        raise MatchDataError("Recent matches could not be loaded from the local database.") from exc

    return [fixture_to_summary(fixture) for fixture in fixtures]


async def search_matches(
    query: str = "",
    competition: str | None = None,
    season: int | None = None,
) -> list[MatchSummary]:
    """Search locally synced fixtures by team, competition, round, and season."""

    provider_competition_id = provider_competition_id_for_code(competition)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            fixtures = await repo.search_fixtures(
                session,
                query_text=query,
                provider_competition_id=provider_competition_id,
                season_year=season,
            )
    except SQLAlchemyError as exc:
        raise MatchDataError("Search results could not be loaded from the local database.") from exc

    return [fixture_to_summary(fixture) for fixture in fixtures]


async def analysis_match(match_id: str) -> tuple[MatchSummary, list[MatchEvent]] | None:
    """Return a locally synced fixture and events for analysis, if present."""

    try:
        provider_fixture_id = int(match_id)
    except (TypeError, ValueError):
        return None

    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            fixture = await session.scalar(
                select(Fixture)
                .options(
                    joinedload(Fixture.competition),
                    joinedload(Fixture.season),
                    joinedload(Fixture.home_team),
                    joinedload(Fixture.away_team),
                    selectinload(Fixture.events).joinedload(FixtureEvent.team),
                )
                .where(
                    Fixture.provider == repo.PROVIDER,
                    Fixture.provider_fixture_id == provider_fixture_id,
                )
            )
    except SQLAlchemyError as exc:
        raise MatchDataError("Match analysis data could not be loaded from the local database.") from exc

    if fixture is None:
        return None
    return fixture_to_summary(fixture), fixture_events_to_summary(fixture.events)


def provider_competition_id_for_code(competition: str | None) -> int | None:
    if not competition:
        return None
    code = competition.strip().upper()
    provider_id = COMPETITION_CODE_TO_PROVIDER_ID.get(code)
    if provider_id is None:
        raise MatchDataError("Unsupported competition.")
    return provider_id


def fixture_to_summary(fixture: Fixture) -> MatchSummary:
    home_team = fixture.home_team
    away_team = fixture.away_team
    competition = fixture.competition
    competition_code = app_competition_code(competition)
    return MatchSummary(
        id=str(fixture.provider_fixture_id),
        home=home_team.name,
        away=away_team.name,
        home_team_id=home_team.provider_team_id,
        away_team_id=away_team.provider_team_id,
        home_short_name=home_team.name,
        away_short_name=away_team.name,
        home_tla=team_code(home_team),
        away_tla=team_code(away_team),
        home_crest=home_team.logo_url,
        away_crest=away_team.logo_url,
        score=score_label(fixture.home_goals, fixture.away_goals),
        score_note=score_note(fixture),
        penalty_score=penalty_score_label(fixture),
        aggregate_score=None,
        half_time_score=score_label(fixture.halftime_home_goals, fixture.halftime_away_goals),
        competition=APP_COMPETITION_NAMES.get(competition.provider_competition_id, competition.name),
        competition_code=competition_code,
        date=fixture.kickoff_at.isoformat(),
        venue=venue_label(fixture),
        round=fixture.round_name,
        season=fixture.season.label,
        status=app_status(fixture.status_short),
    )


def app_competition_code(competition: Competition) -> str:
    return PROVIDER_ID_TO_COMPETITION_CODE.get(
        competition.provider_competition_id,
        competition.code or str(competition.provider_competition_id),
    )


def team_code(team: Team) -> str | None:
    value = team.code
    return value.strip().upper() if isinstance(value, str) and value.strip() else None


def score_label(home: int | None, away: int | None) -> str | None:
    if home is None or away is None:
        return None
    return f"{home}-{away}"


def score_note(fixture: Fixture) -> str | None:
    if fixture.status_short == "AET":
        return "AET"
    if fixture.status_short == "PEN":
        return "AET"
    return None


def penalty_score_label(fixture: Fixture) -> str | None:
    if fixture.penalty_home_goals is None or fixture.penalty_away_goals is None:
        return None
    home = fixture.home_team
    away = fixture.away_team
    winner = home if fixture.penalty_home_goals > fixture.penalty_away_goals else away
    return f"{team_code(winner) or winner.name} won {fixture.penalty_home_goals}-{fixture.penalty_away_goals} on penalties"


def venue_label(fixture: Fixture) -> str | None:
    return " - ".join(part for part in [fixture.venue_name, fixture.venue_city] if part) or None


def app_status(status_short: str | None) -> str | None:
    if status_short in {"FT", "AET", "PEN"}:
        return "FINISHED"
    return status_short


def fixture_events_to_summary(events: list[FixtureEvent]) -> list[MatchEvent]:
    return [
        MatchEvent(
            minute=event.minute or 0,
            type=event_type(event),
            description=event_description(event),
        )
        for event in sorted(events, key=lambda item: ((item.minute or 0), (item.extra_minute or 0), item.id))
        if event.type in {"Goal", "Card"}
    ]


def event_type(event: FixtureEvent) -> str:
    if event.type == "Goal":
        return "goal"
    detail = (event.detail or "").lower()
    if "red" in detail:
        return "red-card"
    return "yellow-card"


def event_description(event: FixtureEvent) -> str:
    minute = f"+{event.extra_minute}" if event.extra_minute else ""
    team = f" ({event.team.name})" if event.team else ""
    player = event.player_name or "Unknown player"
    detail = event.detail or event.type
    return f"{player}{minute} - {detail}{team}"
