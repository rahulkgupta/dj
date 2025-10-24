#!/usr/bin/env python3
"""
Initialise the project database by creating the SQLAlchemy schema and verifying
connectivity. Requires the DATABASE_URL environment variable (or --url).
"""

import argparse
import os
import sys

from database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise the DJ audio tagger database.")
    parser.add_argument(
        "--url",
        help="Database connection string. Defaults to DATABASE_URL environment variable.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display basic job statistics after initialisation completes.",
    )
    args = parser.parse_args()

    database_url = args.url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set and --url was not provided.")

    db = Database(database_url)
    print("✓ Database schema available.")

    if args.stats:
        stats = db.get_job_stats()
        print("Job statistics:")
        for item in stats["job_statistics"]:
            status = item["status"]
            count = item["count"]
            avg_time = item.get("avg_time")
            if avg_time is not None:
                print(f"  - {status}: {count} jobs (avg {avg_time:.2f}s)")
            else:
                print(f"  - {status}: {count} jobs")
        print(f"Total songs: {stats['total_songs']}")


if __name__ == "__main__":
    # Ensure project root is on sys.path so database module resolves when executed elsewhere.
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    if PROJECT_ROOT not in sys.path:
        sys.path.append(PROJECT_ROOT)
    main()
