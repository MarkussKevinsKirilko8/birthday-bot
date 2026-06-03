from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from app.models import Message

logger = logging.getLogger(__name__)


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0
    failures: list = field(default_factory=list)  # list[(chat_id, error_str)]


async def send_all(bot, messages: list[Message], delay: float = 0.05) -> SendReport:
    report = SendReport()
    for m in messages:
        try:
            await bot.send_message(chat_id=m.chat_id, text=m.text)
            report.sent += 1
        except Exception as e:  # noqa: BLE001 — one failure must not stop the run
            report.failed += 1
            report.failures.append((m.chat_id, str(e)))
            logger.error("send to %s failed: %s", m.chat_id, e)
        if delay:
            await asyncio.sleep(delay)
    return report
