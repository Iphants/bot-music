from __future__ import annotations
import asyncio
import traceback
import discord
import asyncio
from . import player, state
from discord.ext import commands
from . import music_cache
from . import player
from . import state
from . import runtime


def setup(bot: commands.Bot) -> None:
    @bot.event
    async def on_ready():
        runtime.set_bot_loop(asyncio.get_running_loop())
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
        if not bot.user:
            return
        if before.channel == after.channel:
            return
        if member.id == bot.user.id:
            if before.channel and not after.channel:
                guild_id = before.channel.guild.id
                player.cancel_idle_leave(guild_id)
                async with player.kunci_lagu(guild_id):
                    state.queue_asli.pop(guild_id, None)
                    state.play_queue.pop(guild_id, None)
                    state.current_playing.pop(guild_id, None)
                    print(f"[CLEAN] bot kelaur paksa dari voice, {guild_id}")
                    return
                
        vc = before.channel.guild.voice_client if before.channel else None
        if not vc:
            return
        guild_id = before.channel.guild.id
        if member.bot and member.id == bot.user.id:
            if before.channel and not after.channel:
                player.cancel_idle_leave(guild_id)
                task = state.gabut.pop(guild_id, None)
                if task and not task.done():
                    task.cancel()
            return
        ch = vc.channel
        if ch is None:
            return
        
        perhitungan_orng = sum(1 for m in ch.members if not m.bot)
        if perhitungan_orng == 0:
            player.schedule_leave(guild_id, vc)
        else:
            task = state.gabut.pop(guild_id, None)
            if task and not task.done():
                task.cancel()

        if member.id != bot.user.id:
            return
        if before.channel and not after.channel:
            guild_id = before.channel.guild.id
            player.cancel_idle_leave(guild_id)
            async with player.kunci_lagu(guild_id):
                state.queue_asli.pop(guild_id, None)
                state.play_queue.pop(guild_id, None)
                state.current_playing.pop(guild_id, None)