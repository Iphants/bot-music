from __future__ import annotations
import asyncio
from app import config, events, runtime
from app.bot_instance import create_bot
from app.commands import basic, playback, queue_cmds, library_kmnd

# ===== RUN BOT =====
async def _run_bot() -> None:
    bot = create_bot()  # satu bot aja dulu
    runtime.set_bot_loop(asyncio.get_running_loop())
    events.setup(bot)
    basic.setup(bot)
    playback.setup(bot)
    queue_cmds.setup(bot)
    library_kmnd.setup(bot)
    try:
        await bot.start(config.discord_token())
    finally:
        await bot.close()

# ===== ENTRYPOINT =====
def main() -> None:
    asyncio.run(_run_bot())

if __name__ == "__main__":
    main()
