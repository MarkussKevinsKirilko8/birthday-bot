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


# ---------------------------------------------------------------------------
# Task 6: Holiday message building
# ---------------------------------------------------------------------------
from app.holidays import HOLIDAYS


def _custom_msg(holiday, d):
    return {
        0: holiday.get("msgDay"),
        2: holiday.get("msg2"),
        7: holiday.get("msg7"),
        14: holiday.get("msg14"),
        21: holiday.get("msg21"),
    }.get(d)


def _advance_prefix(holiday, d):
    if d >= 7:
        word = "три недели" if d == 21 else "две недели" if d == 14 else "неделю"
        return f"📅 Через {word} — {holiday['icon']} {holiday['name']}!"
    return f"⏰ Послезавтра — {holiday['icon']} {holiday['name']}!"


def build_holiday_messages(rows: list[Employee], today, management_chat_id) -> list[Message]:
    results: list[Message] = []
    for holiday in HOLIDAYS:
        hd = parse_ddmm(holiday["date"])
        if not hd:
            continue
        d = diff_days(hd[0], hd[1], today)
        if d not in holiday["remind_days"]:
            continue

        all_dept_chats, all_extra_chats = [], []
        names_by_dept, names_by_extra = {}, {}
        all_names, all_names_country = [], []

        for e in rows:
            if not e.name:
                continue
            if holiday["gender"] != "all" and e.gender != holiday["gender"]:
                continue
            all_names.append(e.name)
            all_names_country.append(f"{e.name} ({e.country})" if e.country else e.name)
            if e.dept_chat_id:
                key = str(e.dept_chat_id).strip()
                if key not in names_by_dept:
                    names_by_dept[key] = []
                    all_dept_chats.append(key)
                names_by_dept[key].append(e.name)
            for extra in e.extra_group_ids():
                if extra not in names_by_extra:
                    names_by_extra[extra] = []
                    all_extra_chats.append(extra)
                names_by_extra[extra].append(e.name)

        custom = _custom_msg(holiday, d)

        if holiday["gender"] != "all":
            if not all_names:
                continue
            if d == 0 and custom:
                for chat, names in names_by_dept.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{custom}\n\nПоздравляем:\n{lst}", chat)
                for chat, names in names_by_extra.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{custom}\n\nПоздравляем:\n{lst}", chat)
                lst = "\n".join(f"  • {n}" for n in all_names_country)
                _add(results, f"{custom}\n\n👥 Поздравляем ({len(all_names)} чел.):\n{lst}", management_chat_id)
            else:
                prefix = custom or _advance_prefix(holiday, d)
                for chat, names in names_by_dept.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{prefix}\n\nПоздравляем:\n{lst}\n\nПодготовьте поздравления! 🎁", chat)
                for chat, names in names_by_extra.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{prefix}\n\nПоздравляем:\n{lst}\n\nПодготовьте поздравления! 🎁", chat)
                lst = "\n".join(f"  • {n}" for n in all_names_country)
                _add(results, f"{prefix}\n\n👥 Поздравляем ({len(all_names)} чел.):\n{lst}\n\nПодготовьте поздравления! 🎁", management_chat_id)
        else:
            if d == 0:
                msg = custom or f"{holiday['icon']} Сегодня — {holiday['name']}!\nС праздником, коллеги! 🎉"
            else:
                msg = custom or _advance_prefix(holiday, d)
            for chat in all_dept_chats:
                _add(results, msg, chat)
            for chat in all_extra_chats:
                _add(results, msg, chat)
            _add(results, msg, management_chat_id)
    return results


# ---------------------------------------------------------------------------
# Task 7: build_messages combiner
# ---------------------------------------------------------------------------
def build_messages(rows, today, management_chat_id) -> list[Message]:
    return (build_birthday_messages(rows, today, management_chat_id)
            + build_holiday_messages(rows, today, management_chat_id))
