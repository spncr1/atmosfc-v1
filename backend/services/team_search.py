"""Search helpers for team names users actually type."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal
import unicodedata


SearchIntentKind = Literal["empty", "competition", "team", "text"]


@dataclass(frozen=True)
class SearchIntent:
    """Structured version of a raw results-page search query."""

    raw_query: str
    clean_query: str
    normalised_query: str
    kind: SearchIntentKind
    query_terms: list[str]
    api_team_query: str | None = None
    competition_code: str | None = None
    should_resolve_team: bool = False


@dataclass(frozen=True)
class ResolvedTeamSearch:
    """Team IDs resolved from search text."""

    provider_team_ids: list[int]
    query_terms: list[str]


TEAM_ALIASES = {
    "psg": ("Paris Saint Germain", "Paris Saint-Germain", "Paris Saint-Germain FC"),
    "paris saint germain": ("Paris Saint Germain", "Paris Saint-Germain", "PSG"),
    "paris saint germain fc": ("Paris Saint Germain", "Paris Saint-Germain FC", "PSG"),
    "man united": ("Manchester United", "Manchester United FC", "Man United", "Man Utd"),
    "man utd": ("Manchester United", "Manchester United FC", "Man United", "Man Utd"),
    "man u": ("Manchester United", "Manchester United FC", "Man United", "Man Utd"),
    "man city": ("Manchester City", "Manchester City FC", "Man City"),
    "barca": ("Barcelona", "FC Barcelona"),
    "atleti": ("Atletico Madrid", "Atlético Madrid", "Club Atletico de Madrid", "Club Atlético de Madrid"),
    "atletico": ("Atletico Madrid", "Atlético Madrid", "Club Atletico de Madrid", "Club Atlético de Madrid"),
    "atletico madrid": ("Atletico Madrid", "Atlético Madrid", "Club Atletico de Madrid", "Club Atlético de Madrid"),
    "bayern": ("Bayern Munich", "FC Bayern München", "Bayern München"),
    "bayern munich": ("Bayern Munich", "FC Bayern München", "Bayern München"),
    "inter": ("Inter Milan", "Internazionale", "FC Internazionale Milano"),
    "inter milan": ("Inter Milan", "Internazionale", "FC Internazionale Milano"),
    "juve": ("Juventus", "Juventus FC"),
    "juventus": ("Juventus", "Juventus FC", "Juve"),
    "juventus fc": ("Juventus", "Juventus FC", "Juve"),
    "spurs": ("Tottenham", "Tottenham Hotspur"),
    "tottenham": ("Tottenham", "Tottenham Hotspur"),
    "st gallen": ("ST Gallen", "ST. Gallen", "FC ST. Gallen", "FC St Gallen"),
}


TEAM_ALIAS_PROVIDER_IDS = {
    "inter": (505,),
    "inter milan": (505,),
}


def parse_search_intent(
    query: str,
    *,
    competition_aliases: dict[str, str] | None = None,
) -> SearchIntent:
    """Classify user search text without resolving it to database IDs yet."""

    clean = " ".join(query.split())
    normalised = normalise_search_text(clean)
    if not normalised:
        return SearchIntent(
            raw_query=query,
            clean_query=clean,
            normalised_query=normalised,
            kind="empty",
            query_terms=[],
            should_resolve_team=False,
        )

    competition_code = (competition_aliases or {}).get(normalised)
    if competition_code:
        return SearchIntent(
            raw_query=query,
            clean_query=clean,
            normalised_query=normalised,
            kind="competition",
            query_terms=[clean, normalised],
            competition_code=competition_code,
            should_resolve_team=False,
        )

    terms = search_terms_for_query(clean)
    is_known_alias = normalised in TEAM_ALIASES
    return SearchIntent(
        raw_query=query,
        clean_query=clean,
        normalised_query=normalised,
        kind="team" if is_known_alias else "text",
        query_terms=terms,
        api_team_query=api_team_search_query(clean),
        should_resolve_team=is_known_alias or looks_like_single_team_query(normalised),
    )


def competition_aliases_for(definitions: list[dict[str, Any]]) -> dict[str, str]:
    """Build competition search aliases from the app's supported competition definitions."""

    aliases: dict[str, str] = {}
    for definition in definitions:
        code = str(definition["code"]).upper()
        values = [
            code,
            definition.get("name"),
            definition.get("short_name"),
        ]
        for value in values:
            normalised = normalise_search_text(str(value or ""))
            if normalised:
                aliases[normalised] = code

    aliases.update({
        "champions league": "CL",
        "ucl": "CL",
        "uefa champions league": "CL",
        "europa league": "EL",
        "uel": "EL",
        "uefa europa league": "EL",
        "conference league": "UECL",
        "uecl": "UECL",
        "uefa conference league": "UECL",
        "epl": "PL",
        "prem": "PL",
        "premier league": "PL",
        "la liga": "PD",
        "laliga": "PD",
        "serie a": "SA",
        "bundesliga": "BL1",
        "ligue 1": "FL1",
        "eredivisie": "NED1",
        "liga portugal": "POR1",
        "primeira liga": "POR1",
        "belgian pro league": "BEL1",
        "jupiler pro league": "BEL1",
        "super lig": "TUR1",
        "turkish super lig": "TUR1",
    })
    return aliases


def search_terms_for_query(query: str) -> list[str]:
    """Return DB search terms for user input, including aliases and punctuation-safe forms."""

    clean = " ".join(query.split())
    normalised = normalise_search_text(clean)
    terms = [clean, normalised]
    terms.extend(TEAM_ALIASES.get(normalised, ()))
    for alias in list(terms):
        terms.append(normalise_search_text(alias))
    return unique_terms(terms)


async def resolve_team_search(intent: SearchIntent, session: Any, client: Any | None = None) -> ResolvedTeamSearch:
    """Resolve a team-ish search to provider team IDs, falling back to API-Football."""

    if not intent.should_resolve_team:
        return ResolvedTeamSearch(provider_team_ids=[], query_terms=intent.query_terms)

    known_team_ids = TEAM_ALIAS_PROVIDER_IDS.get(intent.normalised_query)
    if known_team_ids:
        return ResolvedTeamSearch(provider_team_ids=list(known_team_ids), query_terms=[])

    from backend.repositories import football_data as repo

    db_teams = await repo.search_teams_by_terms(session, intent.query_terms)
    provider_team_ids = [team.provider_team_id for team in db_teams]
    if provider_team_ids:
        return ResolvedTeamSearch(provider_team_ids=unique_ints(provider_team_ids), query_terms=[])

    if client is None or not intent.api_team_query:
        return ResolvedTeamSearch(provider_team_ids=[], query_terms=intent.query_terms)

    rows = await client.teams(search=intent.api_team_query)
    team_row = select_team_search_candidate(rows, intent.api_team_query)
    if team_row is None:
        return ResolvedTeamSearch(provider_team_ids=[], query_terms=intent.query_terms)

    team_id = int((team_row.get("team") or {})["id"])
    return ResolvedTeamSearch(provider_team_ids=[team_id], query_terms=[])


def api_team_search_query(query: str) -> str:
    """Return an API-Football-safe team search string."""

    normalised = normalise_search_text(query)
    aliases = TEAM_ALIASES.get(normalised)
    if aliases:
        return api_safe_query(aliases[0])
    return api_safe_query(normalised)


def select_team_search_candidate(rows: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    if not rows:
        return None
    clean_query = normalise_search_text(query)
    ranked = sorted(rows, key=lambda row: team_candidate_score(row, clean_query), reverse=True)
    return ranked[0]


def team_candidate_score(row: dict[str, Any], clean_query: str) -> tuple[int, int]:
    team = row.get("team") or {}
    name = normalise_search_text(team.get("name") or "")
    code = normalise_search_text(team.get("code") or "")
    is_national = bool(team.get("national"))
    penalty = int(is_national) + int(" w" in name or " u" in name or " youth" in name)
    if name == clean_query or code == clean_query:
        quality = 5
    elif name.startswith(clean_query):
        quality = 4
    elif clean_query in name:
        quality = 3
    elif code and clean_query in code:
        quality = 2
    else:
        quality = 1
    return quality, -penalty


def normalise_search_text(value: str) -> str:
    normalised = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalised.encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", ascii_value).lower().split())


def api_safe_query(value: str) -> str:
    return " ".join(re.sub(r"[^a-zA-Z0-9 ]+", " ", value or "").split())


def looks_like_single_team_query(normalised: str) -> bool:
    if not normalised:
        return False
    separators = {" vs ", " v ", " versus ", " against "}
    padded = f" {normalised} "
    if any(separator in padded for separator in separators):
        return False
    return len(normalised.split()) <= 4


def unique_terms(values: list[str]) -> list[str]:
    seen = set()
    terms = []
    for value in values:
        clean = " ".join(str(value or "").split())
        if len(clean) < 2:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(clean)
    return terms


def unique_ints(values: list[int]) -> list[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
