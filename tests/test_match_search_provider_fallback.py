from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from backend.providers.errors import ProviderRequestError, ProviderResponseError
from backend.services.matches import search_matches
from backend.services.team_search import ResolvedTeamSearch


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def commit(self):
        return None


def fake_sessionmaker():
    return FakeSession()


class MatchSearchProviderFallbackTests(unittest.IsolatedAsyncioTestCase):
    @patch("backend.services.matches.fixtures_to_summaries", return_value=["stored match"])
    @patch("backend.services.matches.visual_profiles_for_fixtures", new_callable=AsyncMock, return_value={})
    @patch("backend.services.matches.repo.search_fixtures", new_callable=AsyncMock, return_value=[object()])
    @patch("backend.services.matches.ensure_archive_scope_synced", new_callable=AsyncMock)
    @patch("backend.services.matches.get_sessionmaker", return_value=fake_sessionmaker)
    async def test_local_results_do_not_wait_for_api_football(
        self,
        _get_sessionmaker,
        ensure_archive_scope_synced,
        search_fixtures,
        _visual_profiles,
        _fixtures_to_summaries,
    ):
        result = await search_matches(query="", competition="PL", season=2026)

        self.assertEqual(result.matches, ["stored match"])
        self.assertEqual(result.notices, [])
        search_fixtures.assert_awaited_once()
        ensure_archive_scope_synced.assert_not_awaited()

    @patch("backend.services.matches.visual_profiles_for_fixtures", new_callable=AsyncMock, return_value={})
    @patch("backend.services.matches.repo.search_fixtures", new_callable=AsyncMock, return_value=[])
    @patch("backend.services.matches.ensure_archive_scope_synced", new_callable=AsyncMock)
    @patch("backend.services.matches.get_sessionmaker", return_value=fake_sessionmaker)
    async def test_competition_search_uses_local_results_when_archive_refresh_fails(
        self,
        _get_sessionmaker,
        ensure_archive_scope_synced,
        search_fixtures,
        _visual_profiles,
    ):
        ensure_archive_scope_synced.side_effect = ProviderResponseError("quota exhausted")

        result = await search_matches(query="", competition="PL", season=2026)

        self.assertEqual(result.matches, [])
        self.assertEqual([notice.type for notice in result.notices], ["provider_refresh_unavailable"])
        search_fixtures.assert_awaited_once()

    @patch("backend.services.matches.visual_profiles_for_fixtures", new_callable=AsyncMock, return_value={})
    @patch("backend.services.matches.repo.search_fixtures", new_callable=AsyncMock, return_value=[])
    @patch("backend.services.matches.ensure_archive_scope_synced", new_callable=AsyncMock)
    @patch("backend.services.matches.resolve_team_search", new_callable=AsyncMock)
    @patch("backend.services.matches.ApiFootballClient")
    @patch("backend.services.matches.get_sessionmaker", return_value=fake_sessionmaker)
    async def test_team_search_uses_local_text_when_provider_resolution_fails(
        self,
        _get_sessionmaker,
        _api_client,
        resolve_team_search,
        ensure_archive_scope_synced,
        search_fixtures,
        _visual_profiles,
    ):
        resolve_team_search.side_effect = [
            ResolvedTeamSearch(provider_team_ids=[], query_terms=["Arsenal"]),
            ProviderRequestError("provider timed out"),
        ]

        result = await search_matches(query="Arsenal", competition="PL", season=2026)

        self.assertEqual(result.matches, [])
        self.assertEqual([notice.type for notice in result.notices], ["provider_refresh_unavailable"])
        self.assertEqual(resolve_team_search.await_count, 2)
        ensure_archive_scope_synced.assert_not_awaited()
        search_fixtures.assert_awaited_once()
        self.assertEqual(search_fixtures.await_args.kwargs["query_terms"], ["Arsenal"])


if __name__ == "__main__":
    unittest.main()
