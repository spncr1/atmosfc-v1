"""Wikidata client for sourced team profile enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from backend.config import get_settings
from backend.providers.errors import ProviderRequestError, ProviderResponseError


@dataclass(frozen=True)
class WikidataSearchResult:
    """One Wikidata search hit."""

    entity_id: str
    label: str
    description: str | None
    aliases: tuple[str, ...]
    concept_uri: str | None


@dataclass(frozen=True)
class WikidataEntity:
    """One loaded Wikidata entity with commonly used fields."""

    entity_id: str
    label: str | None
    description: str | None
    aliases: tuple[str, ...]
    claims: dict[str, Any]
    sitelinks: dict[str, Any]
    raw: dict[str, Any]


class WikidataClient:
    """Small async client for public Wikidata read endpoints."""

    def __init__(
        self,
        *,
        api_url: str | None = None,
        entity_data_url: str | None = None,
        user_agent: str | None = None,
        timeout: float = 12.0,
    ) -> None:
        settings = get_settings()
        self.api_url = api_url or settings.wikidata_api_url
        self.entity_data_url = entity_data_url or settings.wikidata_entity_data_url
        self.timeout = timeout
        self.headers = {
            "Accept": "application/json",
            "User-Agent": user_agent or settings.wikimedia_user_agent,
        }

    async def search_entities(
        self,
        query: str,
        *,
        language: str = "en",
        limit: int = 8,
    ) -> list[WikidataSearchResult]:
        """Search Wikidata items by label/alias."""

        clean_query = query.strip()
        if not clean_query:
            return []

        data = await self.get_json(
            self.api_url,
            params={
                "action": "wbsearchentities",
                "format": "json",
                "language": language,
                "uselang": language,
                "type": "item",
                "search": clean_query,
                "limit": max(1, min(limit, 20)),
            },
        )
        search = data.get("search", [])
        if not isinstance(search, list):
            raise ProviderResponseError("Wikidata search response was not a list.")

        return [search_result(row) for row in search if isinstance(row, dict) and row.get("id")]

    async def entity(self, entity_id: str) -> WikidataEntity:
        """Load one Wikidata entity by QID."""

        clean_entity_id = entity_id.strip().upper()
        if not clean_entity_id.startswith("Q"):
            raise ProviderResponseError(f"Invalid Wikidata entity ID: {entity_id}")

        data = await self.get_json(self.entity_data_url.format(entity_id=clean_entity_id))
        entities = data.get("entities")
        if not isinstance(entities, dict):
            raise ProviderResponseError("Wikidata entity response did not include entities.")
        raw_entity = entities.get(clean_entity_id)
        if not isinstance(raw_entity, dict):
            raise ProviderResponseError(f"Wikidata entity {clean_entity_id} was not found.")

        return entity_from_raw(clean_entity_id, raw_entity)

    async def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Request JSON from Wikidata."""

        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value is not None and value != ""
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                response = await client.get(url, params=clean_params)
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Wikidata request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderResponseError(f"Wikidata returned HTTP {response.status_code}: {_trim(response.text)}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Wikidata returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise ProviderResponseError("Wikidata response was not an object.")
        return data


def search_result(row: dict[str, Any]) -> WikidataSearchResult:
    aliases = row.get("aliases") or []
    if not isinstance(aliases, list):
        aliases = []
    return WikidataSearchResult(
        entity_id=str(row["id"]),
        label=str(row.get("label") or ""),
        description=row.get("description"),
        aliases=tuple(str(alias) for alias in aliases if alias),
        concept_uri=row.get("concepturi"),
    )


def entity_from_raw(entity_id: str, raw_entity: dict[str, Any]) -> WikidataEntity:
    return WikidataEntity(
        entity_id=entity_id,
        label=language_value(raw_entity.get("labels"), "en"),
        description=language_value(raw_entity.get("descriptions"), "en"),
        aliases=tuple(language_aliases(raw_entity.get("aliases"), "en")),
        claims=raw_entity.get("claims") if isinstance(raw_entity.get("claims"), dict) else {},
        sitelinks=raw_entity.get("sitelinks") if isinstance(raw_entity.get("sitelinks"), dict) else {},
        raw=raw_entity,
    )


def language_value(values: Any, language: str) -> str | None:
    if not isinstance(values, dict):
        return None
    value = values.get(language)
    if not isinstance(value, dict):
        return None
    text = value.get("value")
    return str(text) if text else None


def language_aliases(values: Any, language: str) -> list[str]:
    if not isinstance(values, dict):
        return []
    aliases = values.get(language)
    if not isinstance(aliases, list):
        return []
    return [
        str(alias["value"])
        for alias in aliases
        if isinstance(alias, dict) and alias.get("value")
    ]


def english_wikipedia_title(entity: WikidataEntity) -> str | None:
    sitelink = entity.sitelinks.get("enwiki")
    if not isinstance(sitelink, dict):
        return None
    title = sitelink.get("title")
    return str(title) if title else None


def english_wikipedia_url(entity: WikidataEntity) -> str | None:
    title = english_wikipedia_title(entity)
    if not title:
        return None
    return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"


def claim_entity_ids(entity: WikidataEntity, property_id: str) -> list[str]:
    values = []
    for claim in entity.claims.get(property_id, []):
        entity_id = claim_entity_id(claim)
        if entity_id:
            values.append(entity_id)
    return values


def claim_strings(entity: WikidataEntity, property_id: str) -> list[str]:
    values = []
    for claim in entity.claims.get(property_id, []):
        value = claim_datavalue(claim)
        if isinstance(value, str) and value:
            values.append(value)
    return values


def claim_time_years(entity: WikidataEntity, property_id: str) -> list[int]:
    years = []
    for claim in entity.claims.get(property_id, []):
        value = claim_datavalue(claim)
        if not isinstance(value, dict):
            continue
        year = year_from_wikidata_time(value.get("time"))
        if year is not None:
            years.append(year)
    return years


def claim_entity_id(claim: dict[str, Any]) -> str | None:
    value = claim_datavalue(claim)
    if not isinstance(value, dict):
        return None
    numeric_id = value.get("numeric-id")
    return f"Q{numeric_id}" if numeric_id is not None else None


def claim_datavalue(claim: dict[str, Any]) -> Any:
    mainsnak = claim.get("mainsnak")
    if not isinstance(mainsnak, dict):
        return None
    datavalue = mainsnak.get("datavalue")
    if not isinstance(datavalue, dict):
        return None
    return datavalue.get("value")


def year_from_wikidata_time(value: Any) -> int | None:
    if not isinstance(value, str) or len(value) < 5:
        return None
    try:
        return int(value[1:5])
    except ValueError:
        return None


def _trim(value: str, limit: int = 500) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= limit else f"{clean[: limit - 1]}..."
