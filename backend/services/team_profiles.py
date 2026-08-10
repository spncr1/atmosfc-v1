"""Team profile reads backed by API-Football facts and sourced enrichment."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from backend.database.models import Team, TeamProfileEnrichment, TeamVisualProfile
from backend.database.session import get_sessionmaker
from backend.models.schemas import TeamProfileResponse
from backend.providers.api_football import ApiFootballClient
from backend.providers.errors import ProviderConfigError, ProviderError, ProviderRequestError, ProviderResponseError
from backend.repositories import football_data as repo
from backend.services.matches import clean_stadium_name
from backend.services.team_profile_resolver import resolve_team_profile_enrichment
from backend.services.team_visuals import ensure_team_visual_profiles, team_visual_response


class TeamProfileError(RuntimeError):
    """Raised when a team profile cannot be loaded."""


class TeamProfileNotFoundError(TeamProfileError):
    """Raised when a requested team does not exist locally or in API-Football."""


class TeamProfileUnavailableError(TeamProfileError):
    """Raised when the team profile source cannot be reached."""


async def team_profile(provider_team_id: int) -> TeamProfileResponse:
    """Return team profile facts, using sourced enrichment when available."""

    if provider_team_id <= 0:
        raise TeamProfileNotFoundError("Team ID must be a positive API-Football team ID.")

    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            team = await repo.team_by_provider_id(session, provider_team_id)
            data_source = "local"
            try:
                rows = await ApiFootballClient().teams(team_id=provider_team_id)
            except (ProviderConfigError, ProviderRequestError, ProviderResponseError) as exc:
                if team is None:
                    raise TeamProfileUnavailableError("Team profile could not be loaded from API-Football.") from exc
                rows = []
            if rows:
                team = await repo.upsert_team(session, rows[0])
                await session.commit()
                data_source = "api_football"
            if team is None:
                raise TeamProfileNotFoundError("Team profile was not found.")
            enrichment = await profile_enrichment(session, team)
            visual_profiles = await ensure_team_visual_profiles(session, [team])
            visual_profile = visual_profiles.get(team.provider_team_id)
            await session.commit()
            return profile_response(
                team,
                enrichment=enrichment,
                data_source=data_source,
                visual_profile=visual_profile,
            )
    except SQLAlchemyError as exc:
        raise TeamProfileUnavailableError("Team profile could not be loaded from the local database.") from exc


async def profile_enrichment(session, team: Team) -> TeamProfileEnrichment | None:
    """Return cached/resolved profile enrichment without blocking basic team facts."""

    try:
        return await resolve_team_profile_enrichment(session, team)
    except (ProviderError, SQLAlchemyError):
        return await repo.team_profile_enrichment_for_team(session, team)


def profile_response(
    team: Team,
    *,
    enrichment: TeamProfileEnrichment | None = None,
    data_source: str,
    visual_profile: TeamVisualProfile | None = None,
) -> TeamProfileResponse:
    stadium = clean_stadium_name(team.venue_name)
    facts = enrichment.facts_json if enrichment and isinstance(enrichment.facts_json, dict) else {}
    venue_label = None
    if stadium and team.venue_city:
        venue_label = f"{stadium}, {team.venue_city}"
    elif stadium or team.venue_city:
        venue_label = stadium or team.venue_city
    official_websites = facts.get("official_websites") if isinstance(facts.get("official_websites"), list) else []
    official_website = official_websites[0] if official_websites else None
    wikidata_description = facts.get("wikidata_description") if isinstance(facts.get("wikidata_description"), str) else None
    profile_source = data_source
    if enrichment and enrichment.wikidata_qid and not enrichment.needs_review:
        profile_source = f"{data_source}+wikidata"

    return TeamProfileResponse(
        provider_team_id=team.provider_team_id,
        name=team.name,
        code=team.code,
        country_name=team.country_name,
        founded=team.founded,
        is_national=team.is_national,
        logo_url=team.logo_url,
        venue_name=stadium,
        venue_city=team.venue_city,
        venue_label=venue_label,
        visual=team_visual_response(visual_profile),
        summary=(enrichment.summary if enrichment else None) or wikidata_description,
        profile_sections=[],
        has_manual_profile=False,
        wikidata_qid=enrichment.wikidata_qid if enrichment else None,
        wikipedia_title=enrichment.wikipedia_title if enrichment else None,
        wikipedia_url=enrichment.wikipedia_url if enrichment else None,
        official_website=official_website,
        profile_confidence=enrichment.confidence if enrichment else None,
        profile_needs_review=bool(enrichment.needs_review) if enrichment else False,
        source_attribution_url=enrichment.attribution_url if enrichment else None,
        license_label=enrichment.license_label if enrichment else None,
        facts=facts,
        data_source=profile_source,
    )
