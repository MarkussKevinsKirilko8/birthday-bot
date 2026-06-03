from __future__ import annotations
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def next_run_at(now: datetime, run_time: str, tz: str) -> datetime:
    hh, mm = (int(x) for x in run_time.split(":"))
    zone = ZoneInfo(tz)
    now = now.astimezone(zone)
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _read(state_file: str) -> dict:
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def already_ran_today(state_file: str, today_iso: str) -> bool:
    return _read(state_file).get("last_run") == today_iso


def mark_ran_today(state_file: str, today_iso: str) -> None:
    os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"last_run": today_iso}, f)
