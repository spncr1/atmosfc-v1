"""App-level match reads backed by the local database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from backend.database.models import Competition, Fixture, FixtureEvent, FixtureEventSyncStatus, Team, YouTubeCommentCache
from backend.database.session import get_sessionmaker
from backend.models.schemas import MatchEvent, MatchSummary, SearchNotice
from backend.providers.api_football import ApiFootballClient
from backend.providers.errors import ProviderConfigError, ProviderRequestError, ProviderResponseError
from backend.repositories import football_data as repo
from backend.services.sync import ensure_archive_scope_synced
from backend.services.team_search import competition_aliases_for, parse_search_intent, resolve_team_search, unique_ints


class MatchDataError(RuntimeError):
    """Raised when locally stored match data cannot satisfy a request."""


ArchiveScopeType = Literal[
    "team_competition_season",
    "team_competition_all_seasons",
    "team_season",
    "team_all_seasons",
    "competition_season",
    "competition_all_seasons",
    "supported_season",
    "supported_all_seasons",
    "text_filtered",
]


@dataclass(frozen=True)
class ArchiveScope:
    """The archive slice a results-page search needs before DB results are trustworthy."""

    scope_type: ArchiveScopeType
    provider_team_ids: tuple[int, ...] = ()
    provider_competition_id: int | None = None
    season_year: int | None = None
    is_archive_addressable: bool = True


@dataclass(frozen=True)
class MatchSearchResult:
    matches: list[MatchSummary]
    notices: list[SearchNotice]


SUPPORTED_COMPETITIONS = [
    {
        "code": "PL",
        "provider_id": 39,
        "name": "Premier League",
        "short_name": "PL",
        "country_name": "England",
        "country_code": "GB-ENG",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/39.png",
    },
    {
        "code": "PD",
        "provider_id": 140,
        "name": "La Liga",
        "short_name": "La Liga",
        "country_name": "Spain",
        "country_code": "ES",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/140.png",
    },
    {
        "code": "BL1",
        "provider_id": 78,
        "name": "Bundesliga",
        "short_name": "Bundesliga",
        "country_name": "Germany",
        "country_code": "DE",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/78.png",
    },
    {
        "code": "SA",
        "provider_id": 135,
        "name": "Serie A",
        "short_name": "Serie A",
        "country_name": "Italy",
        "country_code": "IT",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/135.png",
    },
    {
        "code": "FL1",
        "provider_id": 61,
        "name": "Ligue 1",
        "short_name": "Ligue 1",
        "country_name": "France",
        "country_code": "FR",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/61.png",
    },
    {
        "code": "NED1",
        "provider_id": 88,
        "name": "Eredivisie",
        "short_name": "Eredivisie",
        "country_name": "Netherlands",
        "country_code": "NL",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/88.png",
    },
    {
        "code": "POR1",
        "provider_id": 94,
        "name": "Liga Portugal",
        "short_name": "Liga Portugal",
        "country_name": "Portugal",
        "country_code": "PT",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/94.png",
    },
    {
        "code": "BEL1",
        "provider_id": 144,
        "name": "Belgian Pro League",
        "short_name": "Belgian Pro League",
        "country_name": "Belgium",
        "country_code": "BE",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/144.png",
    },
    {
        "code": "TUR1",
        "provider_id": 203,
        "name": "Turkish Super Lig",
        "short_name": "Super Lig",
        "country_name": "Turkey",
        "country_code": "TR",
        "group": "Domestic leagues",
        "logo_url": "https://media.api-sports.io/football/leagues/203.png",
    },
    {
        "code": "CL",
        "provider_id": 2,
        "name": "UEFA Champions League",
        "short_name": "UCL",
        "country_name": "World",
        "country_code": None,
        "group": "European competitions",
        "logo_url": "https://media.api-sports.io/football/leagues/2.png",
    },
    {
        "code": "EL",
        "provider_id": 3,
        "name": "UEFA Europa League",
        "short_name": "UEL",
        "country_name": "World",
        "country_code": None,
        "group": "European competitions",
        "logo_url": "https://media.api-sports.io/football/leagues/3.png",
    },
    {
        "code": "UECL",
        "provider_id": 848,
        "name": "UEFA Conference League",
        "short_name": "UECL",
        "country_name": "World",
        "country_code": None,
        "group": "European competitions",
        "logo_url": "https://media.api-sports.io/football/leagues/848.png",
    },
]


COMPETITION_CODE_TO_PROVIDER_ID = {
    competition["code"]: competition["provider_id"]
    for competition in SUPPORTED_COMPETITIONS
}
COMPETITION_CODE_TO_PROVIDER_ID.update({
    "UCL": 2,
})

PROVIDER_ID_TO_COMPETITION_CODE = {
    competition["provider_id"]: competition["code"]
    for competition in SUPPORTED_COMPETITIONS
}
APP_COMPETITION_NAMES = {
    competition["provider_id"]: competition["name"]
    for competition in SUPPORTED_COMPETITIONS
}
COMPETITION_SEARCH_ALIASES = competition_aliases_for(SUPPORTED_COMPETITIONS)


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

    return fixtures_to_summaries(fixtures)


async def search_matches(
    query: str = "",
    competition: str | None = None,
    season: int | None = None,
) -> MatchSearchResult:
    """Search locally synced fixtures by team, competition, round, and season."""

    intent = parse_search_intent(query, competition_aliases=COMPETITION_SEARCH_ALIASES)
    effective_competition = competition or intent.competition_code
    provider_competition_id = provider_competition_id_for_code(effective_competition)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            client = ApiFootballClient() if intent.should_resolve_team else None
            resolved_team = await resolve_team_search(intent, session, client)
            archive_scope = archive_scope_for(
                intent_kind=intent.kind,
                provider_team_ids=resolved_team.provider_team_ids,
                provider_competition_id=provider_competition_id,
                season_year=season,
            )
            sync_result = await ensure_archive_scope_synced(
                scope_type=archive_scope.scope_type,
                provider_team_ids=archive_scope.provider_team_ids,
                provider_competition_id=archive_scope.provider_competition_id,
                season_year=archive_scope.season_year,
                is_archive_addressable=archive_scope.is_archive_addressable,
            )
            query_terms = query_terms_for_scope(intent.kind, resolved_team.query_terms, archive_scope)
            fixtures = await repo.search_fixtures(
                session,
                query_text=query,
                query_terms=query_terms,
                provider_team_ids=resolved_team.provider_team_ids,
                provider_competition_id=provider_competition_id,
                season_year=season,
            )
    except SQLAlchemyError as exc:
        raise MatchDataError("Search results could not be loaded from the local database.") from exc
    except (ProviderConfigError, ProviderRequestError, ProviderResponseError) as exc:
        raise MatchDataError("Search identity could not be resolved through API-Football.") from exc

    return MatchSearchResult(
        matches=fixtures_to_summaries(fixtures),
        notices=search_notices_from_sync_result(sync_result),
    )


def archive_scope_for(
    *,
    intent_kind: str,
    provider_team_ids: list[int],
    provider_competition_id: int | None,
    season_year: int | None,
) -> ArchiveScope:
    """Return the archive slice that must be complete for a results search."""

    team_ids = tuple(unique_ints(provider_team_ids))
    if team_ids:
        if provider_competition_id is not None and season_year is not None:
            return ArchiveScope(
                scope_type="team_competition_season",
                provider_team_ids=team_ids,
                provider_competition_id=provider_competition_id,
                season_year=season_year,
            )
        if provider_competition_id is not None:
            return ArchiveScope(
                scope_type="team_competition_all_seasons",
                provider_team_ids=team_ids,
                provider_competition_id=provider_competition_id,
            )
        if season_year is not None:
            return ArchiveScope(
                scope_type="team_season",
                provider_team_ids=team_ids,
                season_year=season_year,
            )
        return ArchiveScope(scope_type="team_all_seasons", provider_team_ids=team_ids)

    if provider_competition_id is not None:
        if season_year is not None:
            return ArchiveScope(
                scope_type="competition_season",
                provider_competition_id=provider_competition_id,
                season_year=season_year,
            )
        return ArchiveScope(
            scope_type="competition_all_seasons",
            provider_competition_id=provider_competition_id,
        )

    if intent_kind == "text":
        return ArchiveScope(
            scope_type="text_filtered",
            season_year=season_year,
            is_archive_addressable=False,
        )

    if season_year is not None:
        return ArchiveScope(scope_type="supported_season", season_year=season_year)

    return ArchiveScope(scope_type="supported_all_seasons")


def query_terms_for_scope(
    intent_kind: str,
    query_terms: list[str],
    archive_scope: ArchiveScope,
) -> list[str]:
    if intent_kind == "competition" and archive_scope.scope_type in {"competition_season", "competition_all_seasons"}:
        return []
    return query_terms


def search_notices_from_sync_result(sync_result: dict) -> list[SearchNotice]:
    synced = sync_result.get("synced") or {}
    coverage_gaps = synced.get("coverage_gaps") or []
    if not coverage_gaps:
        return []

    first_gap = coverage_gaps[0]
    competition_name = APP_COMPETITION_NAMES.get(
        first_gap.get("provider_competition_id"),
        "that competition",
    )
    season = season_label(first_gap["season_year"]) if first_gap.get("season_year") is not None else "that season"
    if sync_result.get("status") == "provider_unavailable":
        return [
            SearchNotice(
                type="provider_coverage_gap",
                title="Provider coverage unavailable",
                message=(
                    f"API-Football does not provide {competition_name} data for {season}. "
                    "This is a provider coverage gap, not a typo or faulty search."
                ),
            )
        ]

    return [
        SearchNotice(
            type="partial_provider_coverage",
            title="Some historical coverage is unavailable",
            message=(
                f"API-Football is missing at least one requested {competition_name} season. "
                "Available matches are still shown below."
            ),
        )
    ]


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
                    joinedload(Fixture.youtube_comment_cache),
                    joinedload(Fixture.event_sync_status),
                    selectinload(Fixture.events).joinedload(FixtureEvent.team),
                )
                .where(
                    Fixture.provider == repo.PROVIDER,
                    Fixture.provider_fixture_id == provider_fixture_id,
                )
            )
            if fixture is None:
                return None

            aggregate_candidates = list(await session.scalars(
                select(Fixture)
                .options(
                    joinedload(Fixture.competition),
                    joinedload(Fixture.season),
                    joinedload(Fixture.home_team),
                    joinedload(Fixture.away_team),
                )
                .where(
                    Fixture.provider == repo.PROVIDER,
                    Fixture.competition_id == fixture.competition_id,
                    Fixture.season_id == fixture.season_id,
                    Fixture.round_name == fixture.round_name,
                    or_(
                        Fixture.home_team_id.in_([fixture.home_team_id, fixture.away_team_id]),
                        Fixture.away_team_id.in_([fixture.home_team_id, fixture.away_team_id]),
                    ),
                )
            ))
            events = list(fixture.events)
            if not events and event_feed_status(fixture.event_sync_status) != "unavailable":
                events = await hydrate_fixture_events(session, fixture)
                await session.commit()
            elif events and event_feed_status(fixture.event_sync_status) != "complete":
                sync_status = await repo.upsert_fixture_event_sync_status(
                    session,
                    fixture,
                    status="complete",
                    event_count=len(events),
                    raw_payload={
                        "source": "local_fixture_events",
                        "provider_fixture_id": fixture.provider_fixture_id,
                    },
                )
                fixture.event_sync_status = sync_status
                await session.commit()

            return (
                fixture_to_summary(fixture, aggregate_score=aggregate_score_from_fixture(fixture, aggregate_candidates)),
                fixture_events_to_summary(events),
            )
    except SQLAlchemyError as exc:
        raise MatchDataError("Match analysis data could not be loaded from the local database.") from exc
    except (ProviderConfigError, ProviderRequestError, ProviderResponseError) as exc:
        raise MatchDataError("Match event data could not be loaded from API-Football.") from exc


async def hydrate_fixture_events(session: AsyncSession, fixture: Fixture) -> list[FixtureEvent]:
    """Fetch and store event timeline data for one locally cached fixture."""

    client = ApiFootballClient()
    raw_events = await client.fixture_events(fixture.provider_fixture_id)
    event_count = await repo.replace_fixture_events(session, fixture, raw_events)
    sync_status = await repo.upsert_fixture_event_sync_status(
        session,
        fixture,
        status="complete" if event_count else "unavailable",
        event_count=event_count,
        raw_payload={
            "source": "api_football",
            "provider_fixture_id": fixture.provider_fixture_id,
        },
    )
    fixture.event_sync_status = sync_status
    events = await session.scalars(
        select(FixtureEvent)
        .options(joinedload(FixtureEvent.team))
        .where(FixtureEvent.fixture_id == fixture.id)
    )
    return list(events)


def provider_competition_id_for_code(competition: str | None) -> int | None:
    if not competition:
        return None
    code = competition.strip().upper()
    provider_id = COMPETITION_CODE_TO_PROVIDER_ID.get(code)
    if provider_id is None:
        raise MatchDataError("Unsupported competition.")
    return provider_id


def fixtures_to_summaries(fixtures: list[Fixture]) -> list[MatchSummary]:
    aggregate_scores = aggregate_scores_for_fixtures(fixtures)
    return [
        fixture_to_summary(fixture, aggregate_score=aggregate_scores.get(fixture.provider_fixture_id))
        for fixture in fixtures
    ]


def fixture_to_summary(fixture: Fixture, aggregate_score: str | None = None) -> MatchSummary:
    home_team = fixture.home_team
    away_team = fixture.away_team
    competition = fixture.competition
    competition_code = app_competition_code(competition)
    youtube_cache = fixture.youtube_comment_cache
    event_sync_status = fixture.event_sync_status
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
        aggregate_score=aggregate_score,
        half_time_score=score_label(fixture.halftime_home_goals, fixture.halftime_away_goals),
        competition=APP_COMPETITION_NAMES.get(competition.provider_competition_id, competition.name),
        competition_code=competition_code,
        date=fixture.kickoff_at.isoformat(),
        venue=venue_label(fixture),
        round=display_round_name(fixture.round_name),
        season=fixture.season.label,
        status=app_status(fixture.status_short),
        youtube_comment_count=youtube_raw_comment_count(youtube_cache),
        youtube_analysed_comment_count=youtube_analysed_comment_count(youtube_cache),
        youtube_comment_status=youtube_comment_status(youtube_cache),
        youtube_checked_at=youtube_checked_at(youtube_cache),
        event_feed_status=event_feed_status(event_sync_status),
        event_feed_checked_at=event_feed_checked_at(event_sync_status),
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


def youtube_raw_comment_count(cache: YouTubeCommentCache | None) -> int | None:
    if cache is None:
        return None
    return cache.raw_comment_count


def youtube_analysed_comment_count(cache: YouTubeCommentCache | None) -> int | None:
    if cache is None:
        return None
    return cache.analysed_comment_count


def youtube_comment_status(cache: YouTubeCommentCache | None) -> str:
    return cache.status if cache is not None else "unchecked"


def youtube_checked_at(cache: YouTubeCommentCache | None) -> str | None:
    if cache is None or cache.checked_at is None:
        return None
    return cache.checked_at.isoformat()


def event_feed_status(status: FixtureEventSyncStatus | None) -> str:
    return status.status if status is not None else "unchecked"


def event_feed_checked_at(status: FixtureEventSyncStatus | None) -> str | None:
    if status is None or status.checked_at is None:
        return None
    return status.checked_at.isoformat()


def display_round_name(round_name: str | None) -> str | None:
    clean = " ".join(str(round_name or "").split())
    if not clean:
        return None

    lower = clean.lower()
    replacements = {
        "16th finals": "Round of 32",
        "8th finals": "Round of 16",
        "quarter-finals": "Quarter-finals",
        "semi-finals": "Semi-finals",
    }
    if lower in replacements:
        return replacements[lower]
    if lower.startswith("group stage"):
        return clean.replace("Group stage", "Group Stage").replace("group stage", "Group Stage")
    return clean


def season_label(year: int) -> str:
    return f"{year}/{str(year + 1)[-2:]}"


def aggregate_scores_for_fixtures(fixtures: list[Fixture]) -> dict[int, str]:
    fixtures_by_id = {fixture.provider_fixture_id: fixture for fixture in fixtures}
    scores: dict[int, str] = {}
    for fixture in fixtures:
        aggregate = aggregate_score_from_fixture(fixture, fixtures)
        if aggregate:
            scores[fixture.provider_fixture_id] = aggregate
    return {
        fixture_id: aggregate
        for fixture_id, aggregate in scores.items()
        if fixture_id in fixtures_by_id
    }


def aggregate_score_from_fixture(fixture: Fixture, candidates: list[Fixture] | None = None) -> str | None:
    other = matching_two_leg_fixture(fixture, candidates or sibling_fixtures(fixture))
    if other is None or not is_second_leg(fixture, other):
        return None

    if same_home_team(fixture, other):
        home_total = safe_goal(fixture.home_goals) + safe_goal(other.home_goals)
        away_total = safe_goal(fixture.away_goals) + safe_goal(other.away_goals)
    else:
        home_total = safe_goal(fixture.home_goals) + safe_goal(other.away_goals)
        away_total = safe_goal(fixture.away_goals) + safe_goal(other.home_goals)

    if home_total > away_total:
        winner = fixture.home_team
        winner_total = home_total
        loser_total = away_total
    else:
        winner = fixture.away_team
        winner_total = away_total
        loser_total = home_total
    return f"{team_code(winner) or winner.name} won {winner_total}-{loser_total} on aggregate"


def sibling_fixtures(fixture: Fixture) -> list[Fixture]:
    return list(getattr(fixture.season, "fixtures", []) or [])


def matching_two_leg_fixture(fixture: Fixture, candidates: list[Fixture]) -> Fixture | None:
    for candidate in candidates:
        if candidate.id == fixture.id:
            continue
        if candidate.competition_id != fixture.competition_id or candidate.season_id != fixture.season_id:
            continue
        if candidate.round_name != fixture.round_name:
            continue
        reversed_order = candidate.home_team_id == fixture.away_team_id and candidate.away_team_id == fixture.home_team_id
        if reversed_order:
            return candidate
    return None


def is_second_leg(fixture: Fixture, other: Fixture) -> bool:
    return fixture.kickoff_at > other.kickoff_at


def same_home_team(fixture: Fixture, other: Fixture) -> bool:
    return fixture.home_team_id == other.home_team_id


def safe_goal(value: int | None) -> int:
    return value or 0


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
