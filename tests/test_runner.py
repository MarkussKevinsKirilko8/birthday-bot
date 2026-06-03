from datetime import date
from app.models import Employee, Message
from app.runner import run_daily


class _FakeBot:
    def __init__(self):
        self.sent = []
    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class _FakeSource:
    def __init__(self, rows):
        self._rows = rows
    def load(self):
        return self._rows


async def test_run_daily_sends_and_reports(tmp_path):
    rows = [Employee("Тимон", "IT", "Энди", "Male", "10.06", "Латвия", "111", "")]
    bot = _FakeBot()
    state = str(tmp_path / "state.json")
    report = await run_daily(
        bot=bot, source=_FakeSource(rows), today=date(2026, 6, 10),
        management_chat_id=999, admin_chat_id=500, state_file=state, delay=0,
    )
    # birthday today -> dept(111) + management(999) + admin summary(500)
    chat_ids = [cid for cid, _ in bot.sent]
    assert 111 in chat_ids and 999 in chat_ids
    assert 500 in chat_ids  # admin summary
    assert report.sent >= 2


async def test_run_daily_admin_alert_on_source_error(tmp_path):
    class _BoomSource:
        def load(self):
            raise RuntimeError("sheet unreachable")
    bot = _FakeBot()
    state = str(tmp_path / "state.json")
    await run_daily(bot=bot, source=_BoomSource(), today=date(2026, 6, 10),
                    management_chat_id=999, admin_chat_id=500, state_file=state, delay=0)
    # admin got an error alert
    assert any(cid == 500 and "❌" in text for cid, text in bot.sent)
