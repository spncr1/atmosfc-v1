"""Frontend metadata sourced from synced football data."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from backend.database.session import get_sessionmaker
from backend.models.schemas import CompetitionOption, MetadataResponse, SeasonOption
from backend.repositories import football_data as repo
from backend.services.matches import SUPPORTED_COMPETITIONS
from backend.services.sync import archive_seasons


class MetadataError(RuntimeError):
    """Raised when frontend metadata cannot be loaded."""


async def frontend_metadata() -> MetadataResponse:
    """Return synced competitions and seasons for frontend filters."""

    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            competitions = await repo.synced_competitions(session)
            synced_seasons = await repo.synced_competition_seasons(session)
    except SQLAlchemyError as exc:
        raise MetadataError("Frontend metadata could not be loaded from the local database.") from exc

    synced_by_provider_id = {competition.provider_competition_id: competition for competition in competitions}
    synced_by_year = {season.year: season for season in synced_seasons}
    return MetadataResponse(
        competitions=[
            CompetitionOption(
                code=str(definition["code"]),
                name=str(definition["name"]),
                short_name=str(definition["short_name"]),
                provider_id=int(definition["provider_id"]),
                logo_url=synced_by_provider_id.get(int(definition["provider_id"])).logo_url
                if int(definition["provider_id"]) in synced_by_provider_id
                else definition.get("logo_url"),
                country_name=definition.get("country_name"),
                country_code=definition.get("country_code"),
                group=str(definition["group"]),
            )
            for definition in SUPPORTED_COMPETITIONS
        ],
        seasons=[
            SeasonOption(
                year=year,
                label=synced_by_year[year].label if year in synced_by_year else repo.season_label(year),
                is_current=synced_by_year[year].is_current if year in synced_by_year else year == archive_seasons()[0],
            )
            for year in archive_seasons()
        ],
    )
