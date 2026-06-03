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
