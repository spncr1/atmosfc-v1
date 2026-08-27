"""Railway process entrypoint for Atmos FC services."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


PROCESS_ALIASES = {
    "web": "web",
    "api": "web",
    "fixture_sync_worker": "fixture_sync_worker",
    "fixture-sync-worker": "fixture_sync_worker",
    "fixtures": "fixture_sync_worker",
    "fixture_sync_once": "fixture_sync_once",
    "fixture-sync-once": "fixture_sync_once",
    "fixture_sync_cron": "fixture_sync_once",
    "fixture-sync-cron": "fixture_sync_once",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start an Atmos FC Railway process.")
    parser.add_argument(
        "--process-type",
        default=os.getenv("ATMOS_PROCESS_TYPE", "web"),
        help="Process to run. Defaults to ATMOS_PROCESS_TYPE or web.",
    )
    return parser.parse_args()


def run_migrations() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


def exec_module(module: str, *args: str) -> None:
    os.execvp(sys.executable, [sys.executable, "-m", module, *args])


def main() -> None:
    args = parse_args()
    raw_process_type = args.process_type.strip().lower()
    process_type = PROCESS_ALIASES.get(raw_process_type)

    if process_type is None:
        valid = ", ".join(sorted(PROCESS_ALIASES))
        raise SystemExit(
            f"Unknown ATMOS_PROCESS_TYPE={raw_process_type!r}. Expected one of: {valid}"
        )

    run_migrations()

    if process_type == "web":
        port = os.getenv("PORT", "8000")
        exec_module(
            "uvicorn",
            "backend.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        )

    if process_type == "fixture_sync_once":
        recent_limit = os.getenv("FIXTURE_SYNC_RECENT_LIMIT", "50")
        exec_module(
            "backend.scripts.run_fixture_sync_worker",
            "--once",
            "--recent-limit",
            recent_limit,
        )

    exec_module("backend.scripts.run_fixture_sync_worker")


if __name__ == "__main__":
    main()
