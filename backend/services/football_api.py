# Football-Data.org API calls

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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
    "EC": "UEFA Europa Conference League",
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
    "uecl": "EC",
    "conference league": "EC",
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
    upper = clean.upper()
    if upper in SUPPORTED_COMPETITIONS:
        return upper
    return COMPETITION_ALIASES.get(clean.lower())


async def search_matches(
    query: str = "",
    competition: Optional[str] = None,
    season: Optional[int] = None,
    limit: int = 24,
) -> List[MatchSummary]:
    # Search supported competitions for matches by team name, competition, and season.

    season_year = season or current_season_start_year()
    if season_year not in allowed_seasons():
        raise FootballDataError("Season must be between 2015 and 2025.")

    requested_code = normalize_competition(competition)
    if competition and requested_code is None:
        raise FootballDataError("Unsupported competition.")
    codes = [requested_code] if requested_code else list(SUPPORTED_COMPETITIONS.keys())
    search_text = query.strip().lower()
    matches: List[MatchSummary] = []
    errors: List[str] = []

    for code in codes:
        try:
            data = await _request_json(f"/competitions/{code}/matches", {"season": season_year})
        except FootballDataError as exc:
            errors.append(str(exc))
            continue
        for raw in data.get("matches", []):
            summary = parse_match(raw)
            if search_text and search_text not in f"{summary.home} {summary.away} {summary.competition}".lower():
                continue
            matches.append(summary)
            if len(matches) >= limit:
                return matches

    if not matches and errors:
        raise FootballDataError(errors[0])
    return matches


async def recent_matches(limit: int = 18) -> List[MatchSummary]:
    # Return recently finished matches from supported competitions.

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
    season = raw.get("season", {})

    return MatchSummary(
        id=str(raw.get("id", "")),
        home=raw.get("homeTeam", {}).get("name", "Home"),
        away=raw.get("awayTeam", {}).get("name", "Away"),
        score=display_score,
        competition=competition.get("name", "Competition"),
        competition_code=competition.get("code", ""),
        date=raw.get("utcDate", ""),
        round=raw.get("matchday") and f"Matchday {raw.get('matchday')}",
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