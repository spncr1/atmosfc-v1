"""Extract missing team visual colours from stored API-Football crest URLs."""

from __future__ import annotations

import argparse
import asyncio

from backend.database.session import get_sessionmaker
from backend.repositories import football_data as repo
from backend.services.team_visuals import ensure_team_visual_profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill team visual colours from crest images.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum teams to process in one run.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        teams = await repo.teams_for_visual_profile_backfill(session, limit=args.limit)
        profiles = await ensure_team_visual_profiles(session, teams)
        await session.commit()
    print({
        "seen": len(teams),
        "profiles": len(profiles),
    })


if __name__ == "__main__":
    asyncio.run(main())
