"""Team visual profile formatting for frontend surfaces."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import colorsys
import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Team
from backend.database.models import TeamVisualProfile
from backend.models.schemas import TeamVisualResponse
from backend.repositories import football_data as repo

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - handled at runtime when dependency is unavailable.
    Image = None
    UnidentifiedImageError = Exception


DEFAULT_PRIMARY = "#747782"
DEFAULT_SECONDARY = "#2B2D33"
PROTECTED_COLOUR_SOURCES = {"manual_registry", "manual_verified"}
PROTECTED_COLOUR_STATUSES = {"known", "manual_verified"}
LOGO_EXTRACTED_SOURCE = "logo_extracted"
LOGO_NEEDS_REVIEW_STATUS = "needs_review"
LOGO_UNKNOWN_STATUS = "unknown"
RETRYABLE_UNKNOWN_REASONS = {
    "pillow_unavailable",
    "logo_fetch_failed",
}


@dataclass(frozen=True)
class ExtractedColours:
    primary: str
    secondary: str | None
    status: str
    reason: str


def team_visual_response(profile: TeamVisualProfile | None) -> TeamVisualResponse:
    """Return a frontend-ready visual profile with honest neutral fallback."""

    raw_primary = clean_hex(profile.primary_colour if profile else None) or DEFAULT_PRIMARY
    raw_secondary = clean_hex(profile.secondary_colour if profile else None) or DEFAULT_SECONDARY
    primary = visible_primary(raw_primary, raw_secondary)

    return TeamVisualResponse(
        primary=primary,
        secondary=raw_secondary,
        primary_colour=raw_primary,
        secondary_colour=raw_secondary,
        glow=with_alpha(primary, 0.24),
        soft_glow=with_alpha(primary, 0.14),
        border=with_alpha(primary, 0.62),
        shadow=with_alpha(primary, 0.34),
        colour_source=profile.colour_source if profile else "fallback",
        colour_status=profile.colour_status if profile else "unknown",
    )


async def ensure_team_visual_profiles(
    session: AsyncSession,
    teams: list[Team],
) -> dict[int, TeamVisualProfile]:
    """Return visual profiles, extracting crest colours for teams without known colours."""

    provider_teams = [team for team in teams if team.provider_team_id is not None]
    profiles = await repo.team_visual_profiles_by_provider_ids(
        session,
        [team.provider_team_id for team in provider_teams],
    )
    for team in provider_teams:
        profile = profiles.get(team.provider_team_id)
        if is_protected_profile(profile):
            continue
        if profile is not None and profile.colour_source == LOGO_EXTRACTED_SOURCE:
            continue
        if profile is not None and profile.colour_source == "fallback_unknown" and not is_retryable_unknown(profile):
            continue
        extracted = await extract_colours_from_logo(team.logo_url)
        profile = await repo.upsert_team_visual_profile(
            session,
            team,
            primary_colour=extracted.primary,
            secondary_colour=extracted.secondary,
            colour_source=LOGO_EXTRACTED_SOURCE if extracted.status != LOGO_UNKNOWN_STATUS else "fallback_unknown",
            colour_status=extracted.status,
            raw_payload={
                "method": "crest_colour_extraction",
                "logo_url": team.logo_url,
                "reason": extracted.reason,
            },
        )
        profiles[team.provider_team_id] = profile
    return profiles


def is_protected_profile(profile: TeamVisualProfile | None) -> bool:
    if profile is None:
        return False
    return profile.colour_source in PROTECTED_COLOUR_SOURCES or profile.colour_status in PROTECTED_COLOUR_STATUSES


def is_retryable_unknown(profile: TeamVisualProfile) -> bool:
    raw_payload = profile.raw_payload if isinstance(profile.raw_payload, dict) else {}
    reason = raw_payload.get("reason")
    return profile.colour_source == "fallback_unknown" and reason in RETRYABLE_UNKNOWN_REASONS


async def extract_colours_from_logo(logo_url: str | None) -> ExtractedColours:
    """Infer practical UI colours from the stored crest/logo URL."""

    if not logo_url:
        return unknown_colours("missing_logo")
    if Image is None:
        return unknown_colours("pillow_unavailable")
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(logo_url)
            response.raise_for_status()
    except httpx.HTTPError:
        return unknown_colours("logo_fetch_failed")
    if len(response.content) > 3_000_000:
        return unknown_colours("logo_too_large")
    return extract_colours_from_image_bytes(response.content)


def extract_colours_from_image_bytes(content: bytes) -> ExtractedColours:
    if Image is None:
        return unknown_colours("pillow_unavailable")
    try:
        image = Image.open(BytesIO(content)).convert("RGBA")
    except (UnidentifiedImageError, OSError):
        return unknown_colours("logo_decode_failed")

    image.thumbnail((128, 128))
    buckets: Counter[tuple[int, int, int]] = Counter()
    for red, green, blue, alpha in image.getdata():
        if alpha < 160:
            continue
        if not usable_colour(red, green, blue):
            continue
        bucket = (round(red / 16) * 16, round(green / 16) * 16, round(blue / 16) * 16)
        buckets[bucket] += colour_weight(red, green, blue)

    if not buckets:
        return unknown_colours("no_usable_colour")

    ranked = [colour for colour, _score in buckets.most_common()]
    primary_rgb = ranked[0]
    secondary_rgb = next(
        (colour for colour in ranked[1:] if colour_distance(primary_rgb, colour) >= 80),
        None,
    )
    primary = rgb_to_hex(primary_rgb)
    secondary = rgb_to_hex(secondary_rgb) if secondary_rgb else None
    status = "auto" if secondary else LOGO_NEEDS_REVIEW_STATUS
    reason = "dominant_logo_colours" if secondary else "single_logo_colour"
    return ExtractedColours(primary=primary, secondary=secondary, status=status, reason=reason)


def unknown_colours(reason: str) -> ExtractedColours:
    return ExtractedColours(
        primary=DEFAULT_PRIMARY,
        secondary=DEFAULT_SECONDARY,
        status=LOGO_UNKNOWN_STATUS,
        reason=reason,
    )


def visible_primary(primary: str, secondary: str) -> str:
    if not is_near_black(primary):
        return primary
    return "#FFFFFF" if is_near_black(secondary) else secondary


def with_alpha(hex_colour: str, alpha: float) -> str:
    rgb = hex_to_rgb(hex_colour)
    if rgb is None:
        rgb = hex_to_rgb(DEFAULT_PRIMARY)
    red, green, blue = rgb or (116, 119, 130)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def clean_hex(value: str | None) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    if not clean.startswith("#"):
        clean = f"#{clean}"
    return clean.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", clean) else None


def is_near_black(hex_colour: str) -> bool:
    rgb = hex_to_rgb(hex_colour)
    if rgb is None:
        return False
    red, green, blue = rgb
    return red <= 42 and green <= 42 and blue <= 42


def usable_colour(red: int, green: int, blue: int) -> bool:
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    del hue
    if value < 0.16 or value > 0.94:
        return False
    if saturation < 0.22:
        return False
    return True


def colour_weight(red: int, green: int, blue: int) -> int:
    _hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    return max(1, round(100 * (0.55 + saturation) * (0.65 + min(value, 0.88))))


def colour_distance(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    return sum((left - right) ** 2 for left, right in zip(first, second)) ** 0.5


def rgb_to_hex(rgb: tuple[int, int, int] | None) -> str | None:
    if rgb is None:
        return None
    red, green, blue = [max(0, min(255, value)) for value in rgb]
    return f"#{red:02X}{green:02X}{blue:02X}"


def hex_to_rgb(hex_colour: str) -> tuple[int, int, int] | None:
    clean = str(hex_colour or "").replace("#", "").strip()
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", clean):
        return None
    return (
        int(clean[0:2], 16),
        int(clean[2:4], 16),
        int(clean[4:6], 16),
    )
