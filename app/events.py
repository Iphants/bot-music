from __future__ import annotations
import asyncio
import traceback
import discord
from discord.ext import commands
from . import config, music_cache, player, runtime, state
from .metadata import get_audio_metadata, get_cover
from .autoalir_store import load_autoalir_state, load_queue, save_queue


def setup(bot: commands.Bot) -> None:
    @bot.event
    async def on_ready():
        runtime.set_bot_loop(asyncio.get_running_loop())
        runtime.set_bot(bot)

        if not getattr(state, "autoalir_state_loaded", False):
            load_autoalir_state()
            load_queue()
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
        embed = discord.Embed(title="Error", color=discord.Color.red())
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            embed.description = f"Argumen '{error.param.name}' wajib diisi"
        elif isinstance(error, commands.CommandOnCooldown):
            embed.description = (
                f"Sabar jembut, coba lagi pas {error.retry_after:.2f} detik."
            )
        elif isinstance(error, commands.MissingPermissions):
            embed.description = (
                f"Permission lu kurang: {', '.join(error.missing_permissions)}"
            )
        elif isinstance(error, commands.CheckFailure):
            embed.description = (
                "lu ga punya akses buat command ini (butuh role DJ / admin server)"
            )
        elif isinstance(error, commands.CommandInvokeError):
            embed.description = "error internal, coba lagi atau lapor admin"
            print(f"[ERROR INTERNAL] Command !{ctx.command} error:")
            traceback.print_exception(
                type(error.original),
                error.original,
                error.original.__traceback__,
            )
        else:
            embed.description = "error internal, coba lagi atau lapor admin"
            print(f"[ERROR UNKNOWN] Command !{ctx.command} error: {error}")
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
                await asyncio.sleep(5)
                guild = bot.get_guild(guild_id)
                vc = guild.voice_client if guild else None

                if vc and vc.is_connected():
                    print(f"[CLEAN] false alarm, bot masih connect {guild_id}")
                    return

                player.cancel_idle_leave(guild_id)

                save_queue(guild_id)

                print(
                    f"[VOICE] bot lepas dari voice {guild_id} (antrean disimpen, ga dihapus)"
                )
            return

        guild = (
            before.channel.guild
            if before.channel
            else after.channel.guild
            if after.channel
            else None
        )
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

    @bot.listen("on_message")
    async def hitung_message_np(message):
        if message.author.bot or not message.guild:
            return
        ch_id = message.channel.id
        if ch_id in state.last_np_message:
            state.pesan_sejak_np[ch_id] = state.pesan_sejak_np.get(ch_id, 0) + 1

    async def preload_cache_async():
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

        print("[CACHE] selesai")
