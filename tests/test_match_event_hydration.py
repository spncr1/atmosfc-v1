from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.providers.errors import ProviderRequestError
from backend.services.matches import ensure_fixture_events_for_analysis


class MatchEventHydrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_events_are_fetched_during_analysis(self):
        session = AsyncMock()
        fixture = SimpleNamespace(
            provider_fixture_id=123,
            event_sync_status=None,
        )
        fetched_events = [object()]

        with patch(
            "backend.services.matches.hydrate_fixture_events",
            new_callable=AsyncMock,
            return_value=fetched_events,
        ) as hydrate:
            result = await ensure_fixture_events_for_analysis(session, fixture, [])

        self.assertIs(result, fetched_events)
        hydrate.assert_awaited_once_with(session, fixture)

    async def test_unavailable_events_are_not_fetched_repeatedly(self):
        session = AsyncMock()
        fixture = SimpleNamespace(
            provider_fixture_id=123,
            event_sync_status=SimpleNamespace(status="unavailable"),
        )

        with patch(
            "backend.services.matches.hydrate_fixture_events",
            new_callable=AsyncMock,
        ) as hydrate:
            result = await ensure_fixture_events_for_analysis(session, fixture, [])

        self.assertEqual(result, [])
        hydrate.assert_not_awaited()

    @patch("backend.services.matches.repo.upsert_fixture_event_sync_status", new_callable=AsyncMock)
    async def test_provider_failure_is_persisted_without_breaking_analysis(self, upsert_status):
        session = AsyncMock()
        fixture = SimpleNamespace(
            provider_fixture_id=123,
            event_sync_status=None,
        )
        failed_status = SimpleNamespace(status="failed")
        upsert_status.return_value = failed_status

        with patch(
            "backend.services.matches.hydrate_fixture_events",
            new_callable=AsyncMock,
            side_effect=ProviderRequestError("provider timed out"),
        ):
            result = await ensure_fixture_events_for_analysis(session, fixture, [])

        self.assertEqual(result, [])
        self.assertIs(fixture.event_sync_status, failed_status)
        upsert_status.assert_awaited_once_with(
            session,
            fixture,
            status="failed",
            event_count=0,
            error_message="provider timed out",
            raw_payload={
                "source": "analysis_on_demand",
                "provider_fixture_id": 123,
            },
        )

    @patch("backend.services.matches.repo.upsert_fixture_event_sync_status", new_callable=AsyncMock)
    async def test_stored_events_repair_incomplete_status(self, upsert_status):
        session = AsyncMock()
        fixture = SimpleNamespace(
            provider_fixture_id=123,
            event_sync_status=SimpleNamespace(status="unchecked"),
        )
        stored_events = [object(), object()]
        complete_status = SimpleNamespace(status="complete")
        upsert_status.return_value = complete_status

        result = await ensure_fixture_events_for_analysis(session, fixture, stored_events)

        self.assertIs(result, stored_events)
        self.assertIs(fixture.event_sync_status, complete_status)
        upsert_status.assert_awaited_once_with(
            session,
            fixture,
            status="complete",
            event_count=2,
            raw_payload={
                "source": "local_fixture_events",
                "provider_fixture_id": 123,
            },
        )


if __name__ == "__main__":
    unittest.main()
