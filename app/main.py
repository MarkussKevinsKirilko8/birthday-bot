from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from aiogram import Bot

from app.config.settings import get_settings
from app.sources.base import get_source
from app.runner import run_daily
from app.scheduler import next_run_at, already_ran_today

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("birthday-bot")

SCHEDULER_ENABLED = True


def make_bot(token: str) -> Bot:
    return Bot(token=token)


async def _do_run():
    s = get_settings()
    bot = make_bot(s.telegram_bot_token)
    today = datetime.now(ZoneInfo(s.timezone)).date()
    try:
        await run_daily(
            bot=bot,
            source=get_source(s),
            today=today,
            management_chat_id=s.management_chat_id,
            admin_chat_id=s.admin_chat_id,
            state_file=s.state_file,
        )
    finally:
        close = getattr(getattr(bot, "session", None), "close", None)
        if close:
            await close()


async def scheduler_loop():
    while SCHEDULER_ENABLED:
        s = get_settings()
        now = datetime.now(ZoneInfo(s.timezone))
        nxt = next_run_at(now, s.run_time, s.timezone)
        sleep_s = (nxt - now).total_seconds()
        logger.info("next run at %s (in %.0f min)", nxt.isoformat(), sleep_s / 60)
        await asyncio.sleep(sleep_s)
        s = get_settings()
        today_iso = datetime.now(ZoneInfo(s.timezone)).date().isoformat()
        if not already_ran_today(s.state_file, today_iso):
            await _do_run()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.run_on_start:
        await _do_run()
    task = asyncio.create_task(scheduler_loop()) if SCHEDULER_ENABLED else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Birthday & Holiday Bot", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run_now():
    await _do_run()
    return {"status": "done"}
