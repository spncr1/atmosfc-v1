"""Continuously sync recent API-Football fixtures into Postgres."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

from backend.services.sync import sync_core_football_data


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the API-Football fixture sync worker.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=env_int("FIXTURE_SYNC_INTERVAL_SECONDS", 1800),
        help="Seconds to wait between sync runs.",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=env_int("FIXTURE_SYNC_RECENT_LIMIT", 30),
        help="Recent fixtures to sync per supported competition/season.",
    )
    parser.add_argument(
        "--include-events",
        action="store_true",
        help="Also sync fixture events. Leave off for fast homepage freshness.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one sync and exit.",
    )
    return parser.parse_args()


async def run_once(recent_limit: int, include_events: bool) -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    print(
        json.dumps(
            {
                "message": "fixture_sync_started",
                "started_at": started_at,
                "recent_limit": recent_limit,
                "include_events": include_events,
            }
        ),
        flush=True,
    )
    result = await sync_core_football_data(
        recent_limit=recent_limit,
        include_events=include_events,
    )
    print(
        json.dumps(
            {
                "message": "fixture_sync_finished",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            },
            default=str,
        ),
        flush=True,
    )


async def main() -> None:
    args = parse_args()
    while True:
        try:
            await run_once(args.recent_limit, args.include_events)
        except Exception as exc:  # noqa: BLE001 - worker must keep running after transient provider errors.
            print(
                json.dumps(
                    {
                        "message": "fixture_sync_failed",
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                        "error": str(exc),
                    }
                ),
                flush=True,
            )

        if args.once:
            return
        await asyncio.sleep(max(60, args.interval_seconds))


if __name__ == "__main__":
    asyncio.run(main())
