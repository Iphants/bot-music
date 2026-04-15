from __future__ import annotations
from app import config, events, runtime
from app.bot_instance import create_bot
from app.commands import basic, playback, queue_cmds

def main() -> None:
    bot = create_bot()
    events.setup(bot)
    basic.setup(bot)
    playback.setup(bot)
    queue_cmds.setup(bot)
    bot.run(config.discord_token())

if __name__ == "__main__":
    main()