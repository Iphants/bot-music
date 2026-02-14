from __future__ import annotations
import traceback
import discord
from discord.ext import commands
from . import music_cache
from . import player
from . import state

def setup(bot: commands.Bot) -> None:
    @bot.event
    async def on_ready():
        print(f"Bot {bot.user} on aktif dinyalakan")
        music_cache.dapetin_cache_file()
    @bot.event
    async def on_command_error(ctx, error):
        embed = discord.Embed(title="Error", color=discord.Color.red())
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            embed.description = f"Argumen '{error.param.name}' wajib diisi"
        elif isinstance(error, commands.CommandOnCooldown):
            embed.description = f"Sabar jembut, coba lagi pas '{error.retry_after:.2f} detik."
        elif isinstance(error, commands.MissingPermissions):
            embed.description = f"Permission lu kurang: '{','.join(error.missing_permissions)}"
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            embed.description = f"error internal: {error.original}"
            print(traceback.format_exc())
        else:
            embed.description = f"error gajelas: {error}"
        try:
            await ctx.send(embed=embed)
        except Exception:
            print("gagal kirim embed error")
    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id != bot.user.id:
            return
        if before.channel and not after.channel:
            guild_id = before.channel.guild.id
            async with player.kunci_lagu(guild_id):
                state.queue_asli.pop(guild_id, None)
                state.play_queue.pop(guild_id, None)
                state.current_playing.pop(guild_id, None)
