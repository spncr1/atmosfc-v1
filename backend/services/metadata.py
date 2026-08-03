"""Frontend metadata sourced from synced football data."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from backend.database.session import get_sessionmaker
from backend.models.schemas import CompetitionOption, MetadataResponse, SeasonOption
from backend.repositories import football_data as repo
from backend.services.matches import APP_COMPETITION_NAMES, PROVIDER_ID_TO_COMPETITION_CODE


class MetadataError(RuntimeError):
    """Raised when frontend metadata cannot be loaded."""


COMPETITION_ORDER = [39, 140, 78, 135, 61, 2, 3, 848]
COMPETITION_SHORT_NAMES = {
    39: "PL",
    140: "La Liga",
    78: "Bundesliga",
    135: "Serie A",
    61: "Ligue 1",
    2: "UCL",
    3: "UEL",
    848: "UECL",
}


async def frontend_metadata() -> MetadataResponse:
    """Return synced competitions and seasons for frontend filters."""

    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            competitions = await repo.synced_competitions(session)
            seasons = await repo.synced_competition_seasons(session)
    except SQLAlchemyError as exc:
        raise MetadataError("Frontend metadata could not be loaded from the local database.") from exc

    known_provider_ids = set(PROVIDER_ID_TO_COMPETITION_CODE)
    ordered_competitions = sorted(
        [competition for competition in competitions if competition.provider_competition_id in known_provider_ids],
        key=lambda competition: COMPETITION_ORDER.index(competition.provider_competition_id)
        if competition.provider_competition_id in COMPETITION_ORDER
        else len(COMPETITION_ORDER),
    )

    return MetadataResponse(
        competitions=[
            CompetitionOption(
                code=PROVIDER_ID_TO_COMPETITION_CODE[competition.provider_competition_id],
                name=APP_COMPETITION_NAMES.get(competition.provider_competition_id, competition.name),
                short_name=COMPETITION_SHORT_NAMES.get(competition.provider_competition_id, competition.name),
                provider_id=competition.provider_competition_id,
                logo_url=competition.logo_url,
            )
            for competition in ordered_competitions
        ],
        seasons=[
            SeasonOption(
                year=season.year,
                label=season.label,
                is_current=season.is_current,
            )
            for season in seasons
        ],
    )
