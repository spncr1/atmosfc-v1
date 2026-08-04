"""Run queued Atmos background jobs once."""

from __future__ import annotations

import argparse
import asyncio

from backend.services.background_jobs import process_queued_jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process queued Atmos background jobs.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum jobs to process.")
    parser.add_argument(
        "--type",
        dest="job_types",
        action="append",
        help="Optional job type filter. Repeat to include multiple types.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    stats = await process_queued_jobs(limit=args.limit, job_types=args.job_types)
    print(stats)


if __name__ == "__main__":
    asyncio.run(main())
