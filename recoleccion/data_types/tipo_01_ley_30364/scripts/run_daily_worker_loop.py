#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from legal_data.config import get_settings


def should_run_now(last_run_date: str | None, now_local: datetime, schedule_hour: int) -> bool:
    return now_local.hour >= schedule_hour and last_run_date != now_local.date().isoformat()


def main() -> None:
    settings = get_settings()
    tz = ZoneInfo(settings.worker_timezone)
    last_run_date: str | None = None

    while True:
        now_local = datetime.now(tz)
        if should_run_now(last_run_date, now_local, settings.worker_schedule_hour):
            subprocess.run(["uv", "run", "python", "scripts/worker_once.py"], check=False)
            last_run_date = now_local.date().isoformat()
        time.sleep(60)


if __name__ == "__main__":
    main()
