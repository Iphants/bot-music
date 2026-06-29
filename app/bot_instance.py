from __future__ import annotations
import discord
from discord.ext import commands
from . import config


def create_bot() -> commands.Bot:
    return commands.Bot(
        command_prefix="!",
        intents=config.build_intents(),
        help_command=None,
        allowed_mentions=discord.AllowedMentions.none(),
    )
