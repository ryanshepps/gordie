#!/usr/bin/env python3
"""
Fetch NHL box scores for the past 30 days.

This script runs fetch_daily_boxscores.py for each of the past 30 days,
processing historical data in chronological order.
"""

import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from module.logger import get_logger

logger = get_logger(__name__, level=logging.INFO)


def main():
    """Run fetch_daily_boxscores.py for the past 30 days."""
    # Get the project root directory (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Calculate date range (past 30 days, starting from yesterday)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=29)  # 30 days total including end_date

    logger.info(f"Fetching box scores from {start_date.date()} to {end_date.date()}")

    success_count = 0
    failure_count = 0
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        logger.info(f"Processing {date_str} ({success_count + failure_count + 1}/30)")

        try:
            # Run the fetch script as a module to ensure proper Python path
            result = subprocess.run(
                [sys.executable, "-m", "scripts.fetch_daily_boxscores", date_str],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(project_root),  # Run from project root
            )

            if result.returncode == 0:
                logger.info(f"✓ Successfully processed {date_str}")
                success_count += 1
            else:
                logger.error(f"✗ Failed to process {date_str}")
                if result.stderr:
                    logger.error(f"Error output: {result.stderr}")
                failure_count += 1

        except Exception as e:
            logger.error(f"✗ Exception processing {date_str}: {e}")
            failure_count += 1

        current_date += timedelta(days=1)

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total days processed: {success_count + failure_count}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failure_count}")
    logger.info("=" * 60)

    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
