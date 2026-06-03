# app/logic.py
from __future__ import annotations
from datetime import date, timedelta


def parse_ddmm(value):
    """Return (day, month) or None. Accepts 'DD.MM' text or a numeric value
    where Excel dropped a trailing zero (14.10 -> 14.1)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        day = int(value)
        month = round((value - day) * 100)
    else:
        s = str(value).strip()
        if "." not in s:
            return None
        parts = s.split(".")
        try:
            day = int(parts[0])
            month = int(parts[1])
        except (ValueError, IndexError):
            return None
    if 1 <= day <= 31 and 1 <= month <= 12:
        return (day, month)
    return None


def diff_days(day: int, month: int, today: date) -> int:
    """Whole days from `today` to day/month of today's year.
    Mimics JS Date overflow: an out-of-range day rolls into the next month."""
    base = date(today.year, month, 1)
    target = base + timedelta(days=day - 1)
    return (target - today).days
