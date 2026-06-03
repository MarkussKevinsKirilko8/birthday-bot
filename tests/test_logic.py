# tests/test_logic.py
from datetime import date
from app.logic import parse_ddmm, diff_days


def test_parse_ddmm_string():
    assert parse_ddmm("26.01") == (26, 1)
    assert parse_ddmm("14.10") == (14, 10)
    assert parse_ddmm(" 03.02 ") == (3, 2)


def test_parse_ddmm_numeric_reconstructs_month():
    # Excel dropped the trailing zero: 14.10 -> 14.1 ; .01 -> 1 (Jan)
    assert parse_ddmm(14.1) == (14, 10)
    assert parse_ddmm(26.01) == (26, 1)
    assert parse_ddmm(8.11) == (8, 11)


def test_parse_ddmm_invalid():
    assert parse_ddmm(None) == None
    assert parse_ddmm("") == None
    assert parse_ddmm("nope") == None
    assert parse_ddmm("40.01") == None
    assert parse_ddmm("10.13") == None


def test_diff_days_basic():
    today = date(2026, 6, 3)
    assert diff_days(3, 6, today) == 0
    assert diff_days(10, 6, today) == 7
    assert diff_days(5, 6, today) == 2


def test_diff_days_overflow_does_not_crash():
    # 31.04 is not a real date; JS rolled it to May 1 — we must not raise
    today = date(2026, 4, 28)
    assert diff_days(31, 4, today) == 3  # Apr has 30 days -> May 1


# ---------------------------------------------------------------------------
# Task 3: Data model
# ---------------------------------------------------------------------------
from app.models import Employee, Message


def test_employee_extra_group_ids_parsing():
    e = Employee(name="X", department="", team_lead="", gender="Male",
                 birthday="01.01", country="", dept_chat_id="111",
                 extra_groups="222, 333 ,")
    assert e.extra_group_ids() == ["222", "333"]
    assert Employee(name="X", department="", team_lead="", gender="",
                    birthday="", country="", dept_chat_id="",
                    extra_groups="").extra_group_ids() == []


def test_message_holds_int_chat_id():
    m = Message(chat_id=123, text="hi")
    assert m.chat_id == 123 and m.text == "hi"


# ---------------------------------------------------------------------------
# Task 4: Birthday message building
# ---------------------------------------------------------------------------
from app.logic import build_birthday_messages

MGMT = 7013407968


def _emp(**kw):
    base = dict(name="Тимон", department="Продажи", team_lead="Рагнар",
                gender="Male", birthday="10.06", country="Казахстан",
                dept_chat_id="111", extra_groups="222")
    base.update(kw)
    return Employee(**base)


def test_birthday_7_days_routing_and_text():
    today = date(2026, 6, 3)  # 7 days before 10.06
    msgs = build_birthday_messages([_emp()], today, MGMT)
    by_chat = {m.chat_id: m.text for m in msgs}
    assert set(by_chat) == {111, 222, MGMT}
    short = ("📅 Через неделю день рождения!\n👤 Тимон\n"
             "🏢 Продажи\n📌 Ответственный: Рагнар\n\nПодготовь поздравление!")
    full = ("📅 Через неделю день рождения!\n👤 Тимон\n"
            "🏢 Продажи\n🌍 Казахстан\n📌 Ответственный: Рагнар\n\nПодготовь поздравление!")
    assert by_chat[111] == short
    assert by_chat[222] == short
    assert by_chat[MGMT] == full


def test_birthday_today_text():
    today = date(2026, 6, 10)
    msgs = build_birthday_messages([_emp(dept_chat_id="", extra_groups="")], today, MGMT)
    assert len(msgs) == 1 and msgs[0].chat_id == MGMT
    assert msgs[0].text.startswith("🎂 Сегодня день рождения!\n👤 Тимон\n")
    assert msgs[0].text.endswith("\nПоздравляй! 🎉")


def test_birthday_no_match_returns_empty():
    today = date(2026, 1, 1)
    assert build_birthday_messages([_emp()], today, MGMT) == []


def test_october_birthday_numeric_is_handled():
    # birthday came in as numeric 14.1 (really 14.10)
    today = date(2026, 10, 7)  # 7 days before 14.10
    msgs = build_birthday_messages([_emp(birthday=14.1, dept_chat_id="", extra_groups="")], today, MGMT)
    assert len(msgs) == 1 and "Через неделю" in msgs[0].text
