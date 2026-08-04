"""Run API-Football sync jobs."""

from __future__ import annotations

import argparse
import asyncio
import json

from backend.services.sync import CORE_COMPETITIONS, historical_seasons, sync_core_football_data
from backend.providers.api_football import ApiFootballClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync API-Football data into Postgres.")
    parser.add_argument("--season", type=int, action="append", help="Season year to sync. Can be used more than once.")
    parser.add_argument("--from-season", type=int, help="Start season year for an inclusive historical sync.")
    parser.add_argument("--to-season", type=int, help="End season year for an inclusive historical sync.")
    parser.add_argument(
        "--competition",
        type=int,
        action="append",
        choices=[target.provider_id for target in CORE_COMPETITIONS],
        help="API-Football league ID to sync. Can be used more than once.",
    )
    parser.add_argument("--recent-limit", type=int, default=3, help="Recent fixtures to sync per competition/season.")
    parser.add_argument("--full-season", action="store_true", help="Sync every finished fixture for selected seasons.")
    parser.add_argument("--skip-events", action="store_true", help="Skip fixture event sync.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    seasons = args.season
    if args.from_season:
        api_seasons = await ApiFootballClient().seasons()
        seasons = historical_seasons(api_seasons, args.from_season, args.to_season)

    result = await sync_core_football_data(
        season_years=seasons,
        recent_limit=None if args.full_season else args.recent_limit,
        include_events=not args.skip_events,
        competition_ids=args.competition,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
