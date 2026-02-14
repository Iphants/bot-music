from __future__ import annotations
import os
import time
import traceback
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
from .. import config
from .. import music_cache
from .. import player
from .. import state

def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def play(ctx, *, nama_file: str):
        voice_client = ctx.voice_client
        if not voice_client:
            await ctx.send("Botnya gada di dalem, pake !join")
            return
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)

        file_rel_path = music_cache.cari_file_cocok(nama_file)
        if not file_rel_path:
            hasil_saran = music_cache.cari_lagu(nama_file)
            if hasil_saran:
                saran = "\n".join([f"-{os.path.basename(f)}" for f in hasil_saran[:20]])
                await ctx.send(f"Blom gw tambahin jir {nama_file}, yang ini kah?\n{saran}")
                return
            else:
                await ctx.send("Blom gw tambahin jir musiknya")
                return

        file_path_full = config.music_root_dir() / file_rel_path
        if not file_path_full.exists():
            await ctx.send("Musiknya corrupt atau hilang jir")
            return

        is_playing_now = voice_client.is_playing() or voice_client.is_paused() or guild_id in state.current_playing
        if is_playing_now:
            state.queue_asli[guild_id].append(file_rel_path)
            state.play_queue[guild_id].append(file_rel_path)
            posisi = len(state.queue_asli[guild_id])
            await ctx.send(f"sabar, embut, nih masuk ke antrian posisi {posisi}: {os.path.basename(file_rel_path)}")
            return

        state.current_playing[guild_id] = file_rel_path
        player.ensure_deques(guild_id)
        try:
            state.current_playing[guild_id] = file_rel_path
            ff_source = FFmpegPCMAudio(
                source=str(file_path_full),
                executable=config.ffmpeg_executable(),
                options="-vn -loglevel panic",
            )
            volume = state.tingkat_suara.get(guild_id, 0.5)
            source = PCMVolumeTransformer(ff_source, volume=volume)
            voice_client.play(source, after=player.partial(player.after_play, guild_id, voice_client))
            await ctx.send(f"Lagi jalanin ini le: {os.path.basename(file_rel_path)}")
        except Exception as e:
            state.current_playing.pop(guild_id, None)
            await ctx.send(f"error anjay {e}")
            print(traceback.format_exc())

    @bot.command()
    async def search(ctx, *, query: str):
        hasil = music_cache.cari_lagu(query)
        if not hasil:
            await ctx.send("Blom gw tambahin jir musiknya")
            return
        format_baris = []
        for file_path in hasil[:20]:
            if "\\" in file_path or "/" in file_path:
                folder = os.path.dirname(file_path)
                nama_file = os.path.basename(file_path)
                format_baris.append(f"-{nama_file}(di {folder})")
            else:
                format_baris.append(f"-{file_path}")
        formatted = "\n".join(format_baris)
        await ctx.send(f"nih ya embut '{query}':\n{formatted}")

    @bot.command()
    async def refresh(ctx):
        state.file_cache = music_cache.buat_music_cache()
        state.cache_timestamp = time.time()
        await ctx.send(f"cache nya lu update nih: {len(state.file_cache)} entries lu mbut")

    @bot.command()
    async def pause(ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await ctx.send("mengheningkan cipta bentar")
        else:
            await ctx.send("tuli kah? gada musiknya")

    @bot.command()
    async def resume(ctx):
        async with player.kunci_lagu(ctx.guild.id):
            voice_client = ctx.voice_client
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await ctx.send("infokan penglanjutan musik")
            else:
                await ctx.send("tuli kah? gada musik yg berhenti")

    @bot.command()
    async def now(ctx):
        async with player.kunci_lagu(ctx.guild.id):
            guild_id = ctx.guild.id
            if guild_id in state.current_playing:
                await ctx.send(f"lu lagi dengerin: {os.path.basename(state.current_playing[guild_id])}")
            else:
                await ctx.send("tuli kah gada musiknya")

    @bot.command()
    async def next(ctx):
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if not voice_client or not voice_client.is_connected():
                await ctx.send("Botnya gada di dalem, pake !join")
                return
            if not voice_client.is_playing() and not voice_client.is_paused():
                await ctx.send("tuli kah? gada musiknya")
                return
            voice_client.stop()
            await ctx.send("skip dah ke lagu berikutnya")

    @bot.command()
    async def volume(ctx, level: int):
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if 0 <= level <= 100:
                state.tingkat_suara[guild_id] = level / 100
                await ctx.send(f"volume lu di atur di {level}")
            else:
                await ctx.send("atur volume sampe 0-100 dongok")

    @bot.command()
    async def repeat(ctx):
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            baru = not state.ulang_lagu.get(guild_id, False)
            state.ulang_lagu[guild_id] = baru
            await ctx.send(f"repeat nya lagi: {'nyala' if baru else 'mati'}")

