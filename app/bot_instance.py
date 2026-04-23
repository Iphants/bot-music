from __future__ import annotations
from discord.ext import commands
from . import config

# ===== CREATE BOT =====
def create_bot() -> commands.Bot:
    return commands.Bot(command_prefix="!", intents=config.build_intents(), help_command=None)
