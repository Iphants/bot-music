from __future__ import annotations
import asyncio
from typing import Optional

_BOT_LOOP: Optional[asyncio.AbstractEventLoop] = None
_BOT = None


def set_bot_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _BOT_LOOP
    _BOT_LOOP = loop


def get_bot_loop() -> asyncio.AbstractEventLoop:
    if _BOT_LOOP is None:
        raise RuntimeError(
            "Bot loop not set. Call set_bot_loop(bot.loop) during startup."
        )
    return _BOT_LOOP


def set_bot(bot) -> None:
    global _BOT
    _BOT = bot


def get_bot():
    return _BOT
