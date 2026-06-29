from __future__ import annotations
import asyncio
from typing import Optional

_BOT_LOOP: Optional[asyncio.AbstractEventLoop] = None
_BOT = None

# simpen loop bot biar callback player/yt dari thread lain bisa manggil coroutine
def set_bot_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _BOT_LOOP
    _BOT_LOOP = loop

# ambil loop yang tadi disimpen
def get_bot_loop() -> asyncio.AbstractEventLoop:
    if _BOT_LOOP is None:
        # kalau nyangkut sini biasanya bot keburu manggil callback sebelum loop diset
        raise RuntimeError("Bot loop not set. Call set_bot_loop(bot.loop) during startup.")
    return _BOT_LOOP

# simpen instance bot buat helper seperti refresh dashboard/live lyrics
def set_bot(bot) -> None:
    global _BOT
    _BOT = bot

# ambil instance bot tanpa muter dependency import antar modul
def get_bot():
    return _BOT
