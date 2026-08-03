"""Run API-Football sync jobs."""

from __future__ import annotations

import argparse
import asyncio
import json

from backend.services.sync import sync_core_football_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync API-Football data into Postgres.")
    parser.add_argument("--season", type=int, action="append", help="Season year to sync. Can be used more than once.")
    parser.add_argument("--recent-limit", type=int, default=3, help="Recent fixtures to sync per competition/season.")
    parser.add_argument("--skip-events", action="store_true", help="Skip fixture event sync.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await sync_core_football_data(
        season_years=args.season,
        recent_limit=args.recent_limit,
        include_events=not args.skip_events,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
