# Football-Data.org API calls

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import re
import unicodedata

import httpx

from backend.config import get_settings
from backend.models.schemas import MatchEvent, MatchSummary

BASE_URL = "https://api.football-data.org/v4"

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
    limit: int = 24,
) -> List[MatchSummary]:
    # Search supported competitions for matches by team name, competition, and season.

    if season and season not in allowed_seasons():
        raise FootballDataError("Season must be between 2015 and 2025.")

    requested_code = normalize_competition(competition)
    if competition and requested_code is None:
        raise FootballDataError("Unsupported competition.")
    codes = [requested_code] if requested_code else SEARCHABLE_COMPETITIONS
    seasons = [season] if season else list(reversed(allowed_seasons()))
    search_terms = _search_terms(query)
    matches: List[MatchSummary] = []
    errors: List[str] = []

    for season_year in seasons:
        season_matches: List[MatchSummary] = []
        for code in codes:
            try:
                data = await _request_json(f"/competitions/{code}/matches", {"season": season_year})
            except FootballDataError as exc:
                errors.append(str(exc))
                continue
            for raw in data.get("matches", []):
                summary = parse_match(raw)
                if search_terms and not _matches_search(summary, search_terms):
                    continue
                season_matches.append(summary)
        matches.extend(sorted(season_matches, key=lambda match: match.date, reverse=True))
        if len(matches) >= limit:
            return matches[:limit]

    if not matches and errors:
        raise FootballDataError(errors[0])
    return sorted(matches, key=lambda match: match.date, reverse=True)[:limit]


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


def parse_match(raw: Dict[str, Any]) -> MatchSummary:
    # Convert a Football-Data.org match object into an Atmos match summary.

    score = raw.get("score", {}).get("fullTime", {})
    home_score = score.get("home")
    away_score = score.get("away")
    display_score = "TBD" if home_score is None or away_score is None else f"{home_score}-{away_score}"
    competition = raw.get("competition", {})
    competition_code = competition.get("code", "")
    season = raw.get("season", {})

    return MatchSummary(
        id=str(raw.get("id", "")),
        home=raw.get("homeTeam", {}).get("name", "Home"),
        away=raw.get("awayTeam", {}).get("name", "Away"),
        score=display_score,
        competition=SUPPORTED_COMPETITIONS.get(competition_code, competition.get("name", "Competition")),
        competition_code=competition_code,
        date=raw.get("utcDate", ""),
        round=_format_round(raw),
        season=_format_season(season.get("startDate")),
        status=raw.get("status"),
    )


def parse_events(raw: Dict[str, Any]) -> List[MatchEvent]:
    # Extract timeline events when the upstream payload includes them.

    events: List[MatchEvent] = []
    for goal in raw.get("goals", []) or []:
        minute = int(goal.get("minute") or 0)
        team = goal.get("team", {}).get("name", "")
        scorer = goal.get("scorer", {}).get("name", "Goal")
        events.append(MatchEvent(minute=minute, type="goal", description=f"{scorer} ({team})"))

    return sorted(events, key=lambda event: event.minute)


def _search_terms(query: str) -> List[str]:
    clean = _normalize_text(query)
    if not clean:
        return []
    return [clean, *TEAM_ALIASES.get(clean, [])]


def _matches_search(match: MatchSummary, terms: List[str]) -> bool:
    haystack = _normalize_text(f"{match.home} {match.away} {match.competition}")
    return any(term in haystack for term in terms)


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
