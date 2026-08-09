#!/usr/bin/env python3
"""UniMate notification scheduler — checks official university pages 3× daily.

Usage:
    python scheduler.py --once              # single run (for cron)
    python scheduler.py --daemon            # long-running, fires at 08:00 / 14:00 / 20:00
    python scheduler.py --once --uni ned_university   # one university only

Cron example (3× daily):
    0 8,14,20 * * * cd /path/to/UniMate && /path/to/venv/bin/python scheduler.py --once
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta

from notifications.job import run_notification_check

logger = logging.getLogger(__name__)

# Local-time check slots (hour, minute).
DEFAULT_SCHEDULE = ((8, 0), (14, 0), (20, 0))


def _next_run_at(now: datetime, schedule=DEFAULT_SCHEDULE) -> datetime:
    candidates: list[datetime] = []
    for hour, minute in schedule:
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot <= now:
            slot += timedelta(days=1)
        candidates.append(slot)
    return min(candidates)


def run_once(university_ids: list[str] | None = None) -> int:
    result = run_notification_check(university_ids=university_ids)
    if result.errors:
        for err in result.errors:
            logger.error(err)
    print(
        f"Checked {result.universities_checked} universities, "
        f"{result.pages_checked} pages, "
        f"{result.changes_found} changes, "
        f"{result.emails_sent} emails sent."
    )
    return 1 if result.errors else 0


def run_daemon(university_ids: list[str] | None = None) -> None:
    logger.info("UniMate notification daemon started (3× daily at 08:00, 14:00, 20:00 local time).")
    while True:
        now = datetime.now()
        nxt = _next_run_at(now)
        sleep_seconds = max(1, int((nxt - now).total_seconds()))
        logger.info("Next notification check at %s (in %s s)", nxt.isoformat(), sleep_seconds)
        time.sleep(sleep_seconds)
        try:
            run_once(university_ids=university_ids)
        except Exception:
            logger.exception("Scheduled notification run failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UniMate university update notification scheduler")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run one check cycle and exit")
    mode.add_argument("--daemon", action="store_true", help="Run continuously on the 3× daily schedule")
    parser.add_argument(
        "--uni",
        action="append",
        dest="universities",
        metavar="UNIVERSITY_ID",
        help="Limit to specific university_id (repeatable)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    uni_ids = args.universities or None
    if args.once:
        return run_once(university_ids=uni_ids)
    run_daemon(university_ids=uni_ids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
