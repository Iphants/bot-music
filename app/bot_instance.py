from __future__ import annotations
from discord.ext import commands
from . import config

# bikin objek botnya doang, command dipasang di tempat lain
def create_bot() -> commands.Bot:
    return commands.Bot(command_prefix="!", intents=config.build_intents(), help_command=None)
