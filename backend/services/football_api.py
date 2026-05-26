# Football-Data.org API calls

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import re
import time
import unicodedata

import httpx

from backend.config import get_settings
from backend.models.schemas import MatchEvent, MatchSummary

BASE_URL = "https://api.football-data.org/v4"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"

SUPPORTED_COMPETITIONS: Dict[str, str] = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "CL": "UEFA Champions League",
    "EL": "UEFA Europa League",
    "UCL": "UEFA Conference League",
}

SEARCHABLE_COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "CL"]
CACHE_TTL_SECONDS = 600
TEAM_CACHE_TTL_SECONDS = 86_400
VENUE_CACHE_TTL_SECONDS = 604_800
_SEARCH_CACHE: Dict[str, tuple[float, List[MatchSummary]]] = {}
_TEAM_CACHE: Dict[int, tuple[float, Dict[str, Any]]] = {}
_VENUE_CACHE: Dict[str, tuple[float, str]] = {}

NEUTRAL_VENUES: Dict[tuple[str, int, str], str] = {
    ("CL", 2025, "FINAL"): "Puskás Aréna, Budapest",
    ("CL", 2024, "FINAL"): "Allianz Arena, Munich",
    ("CL", 2023, "FINAL"): "Wembley Stadium, London",
    ("CL", 2022, "FINAL"): "Atatürk Olympic Stadium, Istanbul",
    ("CL", 2021, "FINAL"): "Stade de France, Saint-Denis",
    ("CL", 2020, "FINAL"): "Estádio do Dragão, Porto",
    ("CL", 2019, "FINAL"): "Estádio da Luz, Lisbon",
    ("CL", 2018, "FINAL"): "Metropolitano Stadium, Madrid",
    ("CL", 2017, "FINAL"): "NSC Olimpiyskiy Stadium, Kyiv",
    ("CL", 2016, "FINAL"): "Millennium Stadium, Cardiff",
    ("CL", 2015, "FINAL"): "San Siro, Milan",
}

COMPETITION_ALIASES: Dict[str, str] = {
    "premier league": "PL",
    "epl": "PL",
    "pl": "PL",
    "la liga": "PD",
    "laliga": "PD",
    "bundesliga": "BL1",
    "serie a": "SA",
    "ligue 1": "FL1",
    "ucl": "CL",
    "champions league": "CL",
    "uel": "EL",
    "europa league": "EL",
    "uecl": "UCL",
    "conference league": "UCL",
}

TEAM_ALIASES: Dict[str, List[str]] = {
    "atleti": ["atletico madrid"],
    "barca": ["barcelona"],
    "bayern": ["bayern munchen", "bayern munich"],
    "inter": ["internazionale", "inter milan"],
    "inter milan": ["internazionale"],
    "man city": ["manchester city"],
    "man utd": ["manchester united"],
    "man united": ["manchester united"],
    "psg": ["paris saint germain"],
    "spurs": ["tottenham hotspur", "tottenham"],
}


class FootballDataError(RuntimeError):
    # Raised when Football-Data.org cannot satisfy a request.
    pass


def current_season_start_year(today: Optional[date] = None) -> int:
    # Return the start year for the active European football season.

    value = today or date.today()
    return value.year if value.month >= 7 else value.year - 1


def allowed_seasons() -> List[int]:
    # Return supported season start years from 2015/16 through 2025/26.

    return list(range(2015, 2026))


def normalize_competition(value: Optional[str]) -> Optional[str]:
    # Convert user-facing competition text into a Football-Data.org code.

    if not value:
        return None
    clean = value.strip()
    alias = COMPETITION_ALIASES.get(clean.lower())
    if alias:
        return alias
    upper = clean.upper()
    if upper in SUPPORTED_COMPETITIONS:
        return upper
    return None


async def search_matches(
    query: str = "",
    competition: Optional[str] = None,
    season: Optional[int] = None,
) -> List[MatchSummary]:
    # Search supported competitions for matches by team name, competition, and season.

    if season and season not in allowed_seasons():
        raise FootballDataError("Season must be between 2015 and 2025.")

    requested_code = normalize_competition(competition)
    if competition and requested_code is None:
        raise FootballDataError("Unsupported competition.")
    cache_key = _search_cache_key(query, requested_code, season)
    cached = _get_cached_search(cache_key)
    if cached is not None:
        return cached

    codes = [requested_code] if requested_code else SEARCHABLE_COMPETITIONS
    seasons = [season] if season else list(reversed(allowed_seasons()))
    search_terms = _search_terms(query)
    matches: List[MatchSummary] = []
    errors: List[str] = []

    for season_year in seasons:
        season_matches: List[MatchSummary] = []
        for code in codes:
            try:
                data = await _request_json(f"/competitions/{code}/matches", {"season": season_year, "status": "FINISHED"})
            except FootballDataError as exc:
                errors.append(str(exc))
                continue
            for raw in data.get("matches", []):
                summary = parse_match(raw)
                if summary.status != "FINISHED":
                    continue
                if search_terms and not _matches_search(summary, search_terms):
                    continue
                season_matches.append(summary)
        matches.extend(sorted(season_matches, key=lambda match: match.date, reverse=True))

    if not matches and errors:
        raise FootballDataError(errors[0])
    sorted_matches = sorted(matches, key=lambda match: match.date, reverse=True)
    _set_cached_search(cache_key, sorted_matches)
    return sorted_matches


async def recent_matches(limit: int = 18, competition: Optional[str] = None) -> List[MatchSummary]:
    # Return recently finished matches from supported competitions.

    requested_code = normalize_competition(competition)
    if competition and requested_code is None:
        raise FootballDataError("Unsupported competition.")
    if requested_code:
        return await _recent_competition_matches(requested_code, limit)
    return await _recent_window_matches(limit)


async def _recent_window_matches(limit: int) -> List[MatchSummary]:
    # Keep the all-competition homepage feed genuinely fresh.

    today = datetime.now(timezone.utc).date()
    matches: List[MatchSummary] = []
    errors: List[str] = []
    for code in SUPPORTED_COMPETITIONS:
        params = {
            "dateFrom": (today - timedelta(days=9)).isoformat(), 
            # ^ ideally a 14-day window would be great here, but FootballData.org's free tier only allows max. 10 days, 
            # so therefore the results will only show the most recent matches up to the last 10 days
            "dateTo": today.isoformat(),
            "competitions": code,
            "status": "FINISHED",
        }
        try:
            data = await _request_json("/matches", params)
        except FootballDataError as exc:
            errors.append(str(exc))
            continue
        matches.extend(parse_match(raw) for raw in data.get("matches", []))
    if not matches and errors:
        raise FootballDataError(errors[0])
    return sorted(matches, key=lambda match: match.date, reverse=True)[:limit]


async def _recent_competition_matches(code: str, limit: int) -> List[MatchSummary]:
    # Competition feeds should show the latest played matches, even during off-season gaps.

    seasons = [year for year in reversed(allowed_seasons()) if year <= current_season_start_year()]

    for season_year in seasons:
        try:
            data = await _request_json(
                f"/competitions/{code}/matches",
                {"season": season_year, "status": "FINISHED"},
            )
        except FootballDataError as exc:
            raise FootballDataError(f"{SUPPORTED_COMPETITIONS[code]} could not be loaded: {exc}") from exc
        matches = [parse_match(raw) for raw in data.get("matches", [])]
        if matches:
            return sorted(matches, key=lambda match: match.date, reverse=True)[:limit]

    return []


async def get_match(match_id: str) -> Dict[str, Any]:
    # Fetch raw match detail for one Football-Data.org match ID.

    return await _request_json(f"/matches/{match_id}")


async def get_team(team_id: int) -> Dict[str, Any]:
    # Fetch Football-Data.org team detail and cache it by real upstream team ID.

    cached = _get_cached_team(team_id)
    if cached is not None:
        return cached

    data = await _request_json(f"/teams/{team_id}")
    _set_cached_team(team_id, data)
    return data


async def get_match_team_details(raw: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    # Best-effort team details for analysis pages; match rendering should survive if either lookup fails.

    home_team_id = _team_id(raw.get("homeTeam", {}))
    away_team_id = _team_id(raw.get("awayTeam", {}))
    home_detail, away_detail = await asyncio.gather(
        _get_team_or_none(home_team_id),
        _get_team_or_none(away_team_id),
    )
    home_detail = await _with_resolved_venue(raw.get("homeTeam", {}), home_detail)
    return home_detail, away_detail


def parse_match(
    raw: Dict[str, Any],
    home_team_detail: Optional[Dict[str, Any]] = None,
    away_team_detail: Optional[Dict[str, Any]] = None,
) -> MatchSummary:
    # Convert a Football-Data.org match object into an Atmos match summary.

    score = raw.get("score", {}).get("fullTime", {})
    half_time = raw.get("score", {}).get("halfTime", {})
    home_score = score.get("home")
    away_score = score.get("away")
    half_home = half_time.get("home")
    half_away = half_time.get("away")
    display_score = "TBD" if home_score is None or away_score is None else f"{home_score}-{away_score}"
    half_time_score = None if half_home is None or half_away is None else f"{half_home}-{half_away}"
    competition = raw.get("competition", {})
    competition_code = competition.get("code", "")
    season = raw.get("season", {})
    home_team = raw.get("homeTeam", {})
    away_team = raw.get("awayTeam", {})
    home_team_id = _team_id(home_team)
    away_team_id = _team_id(away_team)

    return MatchSummary(
        id=str(raw.get("id", "")),
        home=home_team.get("name", "Home"),
        away=away_team.get("name", "Away"),
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_short_name=_team_short_name(home_team, home_team_detail),
        away_short_name=_team_short_name(away_team, away_team_detail),
        home_crest=home_team.get("crest") or _team_detail_value(home_team_detail, "crest"),
        away_crest=away_team.get("crest") or _team_detail_value(away_team_detail, "crest"),
        score=display_score,
        half_time_score=half_time_score,
        competition=SUPPORTED_COMPETITIONS.get(competition_code, competition.get("name", "Competition")),
        competition_code=competition_code,
        date=raw.get("utcDate", ""),
        venue=_resolve_venue(raw, home_team_detail),
        round=_format_round(raw),
        season=_format_season(season.get("startDate")),
        status=raw.get("status"),
    )


def parse_events(raw: Dict[str, Any]) -> List[MatchEvent]:
    # Extract timeline events when the upstream payload includes them.

    events: List[MatchEvent] = []
    for goal in raw.get("goals", []) or []:
        minute = _event_minute(goal)
        scorer = goal.get("scorer", {}).get("name") or "Goal"
        team = _clean_team_name(goal.get("team", {}).get("name", ""))
        score = goal.get("score") or {}
        score_label = _event_score(score)
        detail = goal.get("type")
        parts = [scorer]
        if team:
            parts.append(team)
        if score_label:
            parts.append(score_label)
        if detail and detail not in {"REGULAR", "PENALTY"}:
            parts.append(_format_stage(detail))
        events.append(MatchEvent(minute=minute, type="goal", description=" — ".join(part for part in parts if part)))

    for card in raw.get("bookings", []) or []:
        minute = _event_minute(card)
        card_type = str(card.get("card", "")).lower()
        event_type = "red-card" if "red" in card_type else "yellow-card"
        player = card.get("player", {}).get("name") or "Card"
        team = _clean_team_name(card.get("team", {}).get("name", ""))
        events.append(MatchEvent(
            minute=minute,
            type=event_type,
            description=" — ".join(part for part in [player, team] if part),
        ))

    return sorted(events, key=lambda event: event.minute)


def _search_terms(query: str) -> List[str]:
    clean = _normalize_text(query)
    if not clean:
        return []
    return [clean, *TEAM_ALIASES.get(clean, [])]


def _matches_search(match: MatchSummary, terms: List[str]) -> bool:
    haystack = _normalize_text(f"{match.home} {match.away} {match.competition}")
    return any(term in haystack for term in terms)


def _event_minute(raw: Dict[str, Any]) -> int:
    minute = raw.get("minute") or raw.get("matchMinute") or 0
    try:
        return int(minute)
    except (TypeError, ValueError):
        return 0


def _event_score(raw: Dict[str, Any]) -> Optional[str]:
    home = raw.get("home")
    away = raw.get("away")
    if home is None or away is None:
        return None
    return f"{home}-{away}"


def _search_cache_key(query: str, competition: Optional[str], season: Optional[int]) -> str:
    return f"{_normalize_text(query)}:{competition or 'all'}:{season or 'all'}"


def _get_cached_search(key: str) -> Optional[List[MatchSummary]]:
    cached = _SEARCH_CACHE.get(key)
    if not cached:
        return None
    expires_at, matches = cached
    if expires_at <= time.monotonic():
        _SEARCH_CACHE.pop(key, None)
        return None
    return matches


def _set_cached_search(key: str, matches: List[MatchSummary]) -> None:
    _SEARCH_CACHE[key] = (time.monotonic() + CACHE_TTL_SECONDS, matches)


def _get_cached_team(team_id: int) -> Optional[Dict[str, Any]]:
    cached = _TEAM_CACHE.get(team_id)
    if not cached:
        return None
    expires_at, team = cached
    if expires_at <= time.monotonic():
        _TEAM_CACHE.pop(team_id, None)
        return None
    return team


def _set_cached_team(team_id: int, team: Dict[str, Any]) -> None:
    _TEAM_CACHE[team_id] = (time.monotonic() + TEAM_CACHE_TTL_SECONDS, team)


def _get_cached_venue(key: str) -> Optional[str]:
    cached = _VENUE_CACHE.get(key)
    if not cached:
        return None
    expires_at, venue = cached
    if expires_at <= time.monotonic():
        _VENUE_CACHE.pop(key, None)
        return None
    return venue


def _set_cached_venue(key: str, venue: str) -> None:
    _VENUE_CACHE[key] = (time.monotonic() + VENUE_CACHE_TTL_SECONDS, venue)


async def _get_team_or_none(team_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if team_id is None:
        return None
    try:
        return await get_team(team_id)
    except FootballDataError:
        return None


async def _with_resolved_venue(team: Dict[str, Any], team_detail: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if team_detail and _team_detail_value(team_detail, "venue"):
        return team_detail

    team_id = _team_id(team)
    primary_name = (
        _team_detail_value(team_detail, "name")
        or team.get("name")
        or _team_detail_value(team_detail, "shortName")
        or team.get("shortName")
    )
    if not primary_name:
        return team_detail

    cache_key = str(team_id) if team_id else _normalize_text(primary_name)
    cached = _get_cached_venue(cache_key)
    if cached:
        detail = dict(team_detail or {})
        detail["venue"] = cached
        return detail

    venue = await _resolve_wikidata_venue(_wikidata_team_name_candidates(team, team_detail))
    if not venue:
        return team_detail

    _set_cached_venue(cache_key, venue)
    detail = dict(team_detail or {})
    detail["venue"] = venue
    return detail


def _wikidata_team_name_candidates(team: Dict[str, Any], team_detail: Optional[Dict[str, Any]]) -> List[str]:
    names = [
        _team_detail_value(team_detail, "name"),
        team.get("name"),
        _team_detail_value(team_detail, "shortName"),
        team.get("shortName"),
        _team_detail_value(team_detail, "tla"),
        team.get("tla"),
    ]
    candidates: List[str] = []
    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        clean = name.strip()
        variants = [
            clean,
            _clean_team_name(clean),
            re.sub(r"\bF\.?C\.?$", "", clean, flags=re.IGNORECASE).strip(),
            f"{_clean_team_name(clean)} football club",
        ]
        for variant in variants:
            normalized = _normalize_text(variant)
            if variant and normalized not in seen:
                candidates.append(variant)
                seen.add(normalized)
    return candidates


async def _resolve_wikidata_venue(team_names: List[str]) -> Optional[str]:
    for team_name in team_names:
        entity_id = await _wikidata_team_entity(team_name)
        if not entity_id:
            continue
        venue_id = await _wikidata_claim_entity(entity_id, "P115")
        if venue_id:
            return await _wikidata_entity_label(venue_id)
    return None


async def _wikidata_team_entity(team_name: str) -> Optional[str]:
    params = {
        "action": "wbsearchentities",
        "search": team_name,
        "language": "en",
        "format": "json",
        "limit": 5,
        "origin": "*",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(WIKIDATA_API_URL, params=params)
        if response.status_code >= 400:
            return None
        for item in response.json().get("search", []):
            description = str(item.get("description", "")).lower()
            label = str(item.get("label", ""))
            if "football" in description or _normalize_text(label) == _normalize_text(team_name):
                return item.get("id")
    except (httpx.HTTPError, ValueError):
        return None
    return None


async def _wikidata_claim_entity(entity_id: str, claim_property: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(WIKIDATA_ENTITY_URL.format(entity_id=entity_id))
        if response.status_code >= 400:
            return None
        entity = response.json().get("entities", {}).get(entity_id, {})
    except (httpx.HTTPError, ValueError):
        return None

    for claim in entity.get("claims", {}).get(claim_property, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        venue_id = value.get("id") if isinstance(value, dict) else None
        if venue_id:
            return venue_id
    return None


async def _wikidata_entity_label(entity_id: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(WIKIDATA_ENTITY_URL.format(entity_id=entity_id))
        if response.status_code >= 400:
            return None
        labels = response.json().get("entities", {}).get(entity_id, {}).get("labels", {})
    except (httpx.HTTPError, ValueError):
        return None

    label = labels.get("en", {}).get("value")
    return label.strip() if isinstance(label, str) and label.strip() else None


def _team_detail_value(team_detail: Optional[Dict[str, Any]], key: str) -> Optional[str]:
    if not team_detail:
        return None
    value = team_detail.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalize_text(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text.lower())).strip()


def _format_round(raw: Dict[str, Any]) -> Optional[str]:
    stage = raw.get("stage")
    matchday = raw.get("matchday")
    code = raw.get("competition", {}).get("code")

    if code in {"CL", "EL", "UCL"} and stage:
        label = _format_stage(stage)
        if label:
            return _with_match_context(label, matchday)
    return matchday and f"Matchday {matchday}"


def _format_stage(stage: str) -> Optional[str]:
    labels = {
        "FINAL": "Final",
        "SEMI_FINALS": "Semi-final",
        "QUARTER_FINALS": "Quarter-final",
        "LAST_16": "Round of 16",
        "LAST_32": "Round of 32",
        "LAST_64": "Round of 64",
        "PLAYOFFS": "Knockout phase play-off",
        "PLAYOFF_ROUND_1": "Play-off round",
        "PLAYOFF_ROUND_2": "Play-off round",
        "GROUP_STAGE": "Group stage",
        "LEAGUE_STAGE": "League phase",
    }
    return labels.get(stage)


def _with_match_context(label: str, matchday: Optional[int]) -> str:
    if label == "Final" or not matchday:
        return label
    if label in {"Group stage", "League phase"}:
        return f"{label} - Matchday {matchday}"
    if matchday == 1:
        return f"{label} first leg"
    if matchday == 2:
        return f"{label} second leg"
    return label


def _resolve_venue(raw: Dict[str, Any], home_team_detail: Optional[Dict[str, Any]]) -> Optional[str]:
    venue = raw.get("venue")
    if isinstance(venue, str) and venue.strip():
        return venue.strip()

    competition_code = raw.get("competition", {}).get("code", "")
    season_year = _season_start_year(raw.get("season", {}).get("startDate"))
    stage = raw.get("stage", "")
    neutral_venue = NEUTRAL_VENUES.get((competition_code, season_year, stage))
    if neutral_venue:
        return neutral_venue

    team_venue = _team_detail_value(home_team_detail, "venue")
    if team_venue:
        return team_venue

    return None


def _team_short_name(team: Dict[str, Any], team_detail: Optional[Dict[str, Any]] = None) -> Optional[str]:
    name = (
        _team_detail_value(team_detail, "shortName")
        or team.get("shortName")
        or _team_detail_value(team_detail, "tla")
        or team.get("tla")
        or _team_detail_value(team_detail, "name")
        or team.get("name")
    )
    return _clean_team_name(name) if name else None


def _team_id(team: Dict[str, Any]) -> Optional[int]:
    value = team.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_team_name(name: str) -> str:
    return (
        name.replace("FC Bayern München", "Bayern Munich")
        .replace("Paris Saint-Germain FC", "PSG")
        .replace("Club Atlético de Madrid", "Atlético Madrid")
        .removeprefix("FC ")
        .removesuffix(" FC")
        .removesuffix(" CF")
        .removesuffix(" AFC")
        .strip()
    )


def _season_start_year(start_date: Optional[str]) -> int:
    if not start_date:
        return 0
    try:
        return int(start_date[:4])
    except ValueError:
        return 0


async def _request_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Request JSON from Football-Data.org with configured credentials.

    settings = get_settings()
    if not settings.football_data_api_key:
        raise FootballDataError("FOOTBALL_DATA_API_KEY is not configured.")

    headers = {"X-Auth-Token": settings.football_data_api_key}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0, headers=headers) as client:
        response = await client.get(path, params=params)
    if response.status_code >= 400:
        raise FootballDataError(f"Football-Data.org returned {response.status_code}: {response.text}")
    return response.json()


def _format_season(start_date: Optional[str]) -> Optional[str]:
    # Format a season start date as 2015/16.

    if not start_date:
        return None
    start_year = int(start_date[:4])
    return f"{start_year}/{str(start_year + 1)[-2:]}"
