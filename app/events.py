from __future__ import annotations
import asyncio
import traceback
import discord
from discord.ext import commands
from . import config, music_cache, player, runtime, state
from .metadata import get_audio_metadata, get_cover
from .autoalir_store import load_autoalir_state


# ===== EVENT SETUP =====
def setup(bot: commands.Bot) -> None:
    @bot.event
    async def on_ready():
        # ===== BOT READY =====
        runtime.set_bot_loop(asyncio.get_running_loop())

        if not getattr(state, "autoalir_state_loaded", False):
            load_autoalir_state()
            state.autoalir_state_loaded = True
            
            print("selera:", state.selera_guild)
            print("terakhir:", state.lagu_terakhir_lokal)
            print("history:", state.history_autoalir)
            print("history_mid:", state.history_mid_autoalir)
            print("history_judul:", state.history_jdul_autoalir)


        print(f"Bot {bot.user} on aktif dinyalakan")
        music_cache.dapetin_cache_file()

        if not getattr(state, "cache_preload_started", False):
            state.cache_preload_started = True
            asyncio.create_task(preload_cache_async())

    @bot.event 
    async def on_command_error(ctx, error):
        # ===== ERROR COMMAND =====
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
        # ===== VOICE UPDATE =====
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

                print(f"[CLEAN] bot keluar paksa dari voice, {guild_id}")
            return

        guild = before.channel.guild if before.channel else after.channel.guild if after.channel else None
        if not guild:
            return
        
        vc = guild.voice_client
        if not vc or not vc.channel:
            return

        guild_id = guild.id
        jumlah_orang = sum(1 for m in vc.channel.members if not m.bot)

        if jumlah_orang == 0:
            player.schedule_leave(guild_id, vc)
        else:
            player.cancel_idle_leave(guild_id)
    
    async def preload_cache_async():
        # ===== PRELOAD CACHE =====
        base = config.music_root_dir()
        cache = music_cache.dapetin_cache_file()
        semua_path = []

        for v in cache.values():
            semua_path.extend(v)
        
        semua_path = list(set(semua_path))
        print(f"[CACHE] mulai preload {len(semua_path)} lagu")

        for i, file_rel in enumerate(semua_path):
            try:
                path = base / file_rel
                kunci = str(path)
                if kunci not in state.metadata_cache:
                    met = get_audio_metadata(path)
                    if met:
                        state.metadata_cache[kunci] = met
                if kunci not in state.cover_cache:
                    cov = get_cover(path)
                    if cov:
                        state.cover_cache[kunci] = cov
                if i % 10 == 0:
                    await asyncio.sleep(0)
            except Exception as e:
                print(f"[CACHE ERROR] {file_rel} -> {e}")

        print ("[CACHE] selesai")
