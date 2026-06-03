import pytest
from app.models import Message
from app.telegram import send_all, SendReport


class _FakeBot:
    def __init__(self, fail_chat_ids=()):
        self.sent = []
        self.fail = set(fail_chat_ids)
    async def send_message(self, chat_id, text):
        if chat_id in self.fail:
            raise RuntimeError("403 Forbidden")
        self.sent.append((chat_id, text))


async def test_send_all_sends_every_message():
    bot = _FakeBot()
    msgs = [Message(1, "a"), Message(2, "b")]
    report = await send_all(bot, msgs, delay=0)
    assert report.sent == 2 and report.failed == 0
    assert bot.sent == [(1, "a"), (2, "b")]


async def test_send_all_continues_on_failure():
    bot = _FakeBot(fail_chat_ids={2})
    msgs = [Message(1, "a"), Message(2, "b"), Message(3, "c")]
    report = await send_all(bot, msgs, delay=0)
    assert report.sent == 2 and report.failed == 1
    assert 2 in [cid for cid, _ in report.failures]
