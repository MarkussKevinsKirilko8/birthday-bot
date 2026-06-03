from datetime import datetime
from zoneinfo import ZoneInfo
from app.scheduler import next_run_at, already_ran_today, mark_ran_today

TZ = "Asia/Tbilisi"


def test_next_run_is_later_today_when_before_run_time():
    now = datetime(2026, 6, 3, 7, 0, tzinfo=ZoneInfo(TZ))
    nxt = next_run_at(now, "09:00", TZ)
    assert nxt.hour == 9 and nxt.day == 3


def test_next_run_is_tomorrow_when_past_run_time():
    now = datetime(2026, 6, 3, 10, 0, tzinfo=ZoneInfo(TZ))
    nxt = next_run_at(now, "09:00", TZ)
    assert nxt.day == 4 and nxt.hour == 9


def test_state_roundtrip(tmp_path):
    state = str(tmp_path / "state.json")
    today = "2026-06-03"
    assert already_ran_today(state, today) is False
    mark_ran_today(state, today)
    assert already_ran_today(state, today) is True
    assert already_ran_today(state, "2026-06-04") is False
