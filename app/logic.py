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


# ---------------------------------------------------------------------------
# Task 4: Birthday message building
# ---------------------------------------------------------------------------
from app.models import Employee, Message

BIRTHDAY_REMIND_DAYS = [7, 2, 0]


def _add(results, text, chat_id):
    if text and chat_id is not None and str(chat_id).strip() != "":
        results.append(Message(chat_id=int(str(chat_id).strip()), text=text))


def _birthday_text(prefix, footer, name, department, team_lead, country=None):
    msg = f"{prefix}\n👤 {name}\n"
    if department:
        msg += f"🏢 {department}\n"
    if country:
        msg += f"🌍 {country}\n"
    if team_lead:
        msg += f"📌 Ответственный: {team_lead}\n"
    msg += f"\n{footer}"
    return msg


_BDAY_FORMS = {
    7: ("📅 Через неделю день рождения!", "Подготовь поздравление!"),
    2: ("⏰ Послезавтра день рождения!", "Не забудь поздравить!"),
    0: ("🎂 Сегодня день рождения!", "Поздравляй! 🎉"),
}


def build_birthday_messages(rows: list[Employee], today, management_chat_id) -> list[Message]:
    results: list[Message] = []
    for e in rows:
        if not e.name or e.birthday in (None, ""):
            continue
        bd = parse_ddmm(e.birthday)
        if not bd:
            continue
        d = diff_days(bd[0], bd[1], today)
        if d not in BIRTHDAY_REMIND_DAYS:
            continue
        prefix, footer = _BDAY_FORMS[d]
        short = _birthday_text(prefix, footer, e.name, e.department, e.team_lead)
        full = _birthday_text(prefix, footer, e.name, e.department, e.team_lead, e.country)
        if e.dept_chat_id:
            _add(results, short, e.dept_chat_id)
        for extra in e.extra_group_ids():
            _add(results, short, extra)
        _add(results, full, management_chat_id)
    return results
