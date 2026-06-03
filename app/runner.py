from __future__ import annotations
import logging
from datetime import date
from app.logic import build_messages
from app.telegram import send_all
from app.scheduler import mark_ran_today

logger = logging.getLogger(__name__)


async def run_daily(*, bot, source, today: date, management_chat_id: int,
                    admin_chat_id: int, state_file: str, delay: float = 0.05):
    try:
        rows = source.load()
    except Exception as e:  # noqa: BLE001
        logger.exception("data source load failed")
        try:
            await bot.send_message(chat_id=admin_chat_id,
                                   text=f"❌ Бот ДР: источник данных недоступен: {e}")
        except Exception:
            logger.exception("admin alert failed")
        return None

    messages = build_messages(rows, today, management_chat_id)
    report = await send_all(bot, messages, delay=delay)

    summary = f"✅ Бот ДР {today.isoformat()}: отправлено {report.sent}"
    if report.failed:
        ids = ", ".join(str(cid) for cid, _ in report.failures)
        summary += f"\n⚠️ не доставлено {report.failed} (chat ids: {ids})"
    try:
        await bot.send_message(chat_id=admin_chat_id, text=summary)
    except Exception:
        logger.exception("admin summary failed")

    mark_ran_today(state_file, today.isoformat())
    return report
