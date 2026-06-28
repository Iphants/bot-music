from __future__ import annotations
import os
import time
import traceback
import discord
import io
import re
from pathlib import Path
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
from .. import config
from .. import music_cache
from .. import player
from .. import state
from ..yt import get_audio_source
from functools import partial
from ..metadata import get_audio_metadata, get_cover
from ..autoalir_store import save_queue
from .. import cover_cache


# nama file cover kecil doang, cuma buat attachment embed
def _nama_cover(cover: bytes) -> str:
    if cover.startswith(b"\x89PNG\r\n\x1a\n"):
        return "cover.png"
    return "cover.jpg"


# kalau user ngasih relative path bener, lewat sini dulu
def _path_langsung(nama_file: str) -> str | None:
    rel_norm = str(nama_file).replace("\\", "/").strip().strip("/")
    if not rel_norm:
        return None

    rel_path = Path(rel_norm)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        return None

    full_path = (config.music_root_dir() / rel_path).resolve()
    root_path = config.music_root_dir().resolve()
    try:
        full_path.relative_to(root_path)
    except ValueError:
        return None
    if full_path.is_file():
        return rel_norm
    return None

# helper kirim embed biar cover attachment ga diulang-ulang
async def _kirim_embed(ctx, embed: discord.Embed, cover: bytes | None) -> None:
    if cover:
        filename = _nama_cover(cover)
        file = discord.File(fp=io.BytesIO(cover), filename=filename)
        embed.set_thumbnail(url=f"attachment://{filename}")
        await ctx.send(embed=embed, file=file)
        return
    await ctx.send(embed=embed)


def fmt_durasi(total):
    if not total:
        return "-"
    menit = int(total) // 60
    detik = int(total) % 60
    return f"{menit}:{detik:02d}"

def nama_queue(item):
    if isinstance(item, dict):
        return item.get("title", "Unknown YouTube")
    
    nama = os.path.basename(str(item))
    nama = os.path.splitext(nama)[0]
    nama = nama.replace("_", " ")
    nama = re.sub(r"^\s*\d+\s*[\.\-_\)\]]*\s*", "", nama)
    nama = re.sub(r"\s+", " ", nama).strip()
    return nama or os.path.basename(str(item))

def elaps_lagu(guild_id):
    mulai = state.started_at.get(guild_id)
    if not mulai:
        return None
    
    ttl_pause = state.total_pause.get(guild_id, 0)
    if guild_id in state.paused_at:
        return max(0, state.paused_at[guild_id] - mulai - ttl_pause)
    return max(0, time.time() - mulai - ttl_pause)

def progres_bar(elapsed, duration, lebar=10):
    if not elapsed or not duration:
        return None
    
    ratio = min(1, max(0, elapsed / duration))
    isi = int(ratio * lebar)
    return "▰" * isi + "▱" * (lebar - isi)

async def create_embed_np(guild_id):
    current = state.current_playing.get(guild_id)
    if not current:
        return None
    
    title = "Unknown"
    artist = None
    album = None
    duration = None
    cover_url = None

    if isinstance(current, dict):
        title = current.get("title", "Unknown")
        artist = current.get("uploader")
        duration = current.get("duration")
        cover_url = current.get("thumbnail")
    else:
        file_rel = str(current)
        file_path_full = config.music_root_dir() / file_rel
        kunci = str(file_path_full)
        if kunci in state.metadata_cache:
            metdat = state.metadata_cache[kunci]
        else:
            metdat = get_audio_metadata(file_path_full)
            if metdat:
                state.metadata_cache[kunci] = metdat
        if metdat:
            title = metdat.get("title") or os.path.basename(file_rel)
            artist = metdat.get("artist")
            album = metdat.get("album")
            duration = metdat.get("duration")
        else:
            title = os.path.basename(file_rel)
        cover_url = await cover_cache.resolve_cover(file_rel)

    desc = title
    if artist:
        desc += f"\noleh {artist}"
    if album:
        desc += f"\nAlbum {album}"
    desc += "\n\n━━━━━━━━━━━━"

    embed = discord.Embed(title="lagi play", description=desc, color=0x41639b,)
    queue_now = list(state.play_queue.get(guild_id, []))
    lines = []
    for i, item in enumerate(queue_now[:5], start=1):
        lines.append(f"{i}, {nama_queue(item)}")
    sisa = len(queue_now) - 5
    if sisa > 0:
        lines.append(f"+ {sisa} lagu lagi...")
    antre_task = "\n".join(lines) if lines else "(kosong)"
    embed.add_field(name="Antrean berikutnya", value=antre_task, inline=False)

    elapsed = elaps_lagu(guild_id)
    bar = progres_bar(elapsed, duration)
    if elapsed is not None and duration:
        progres_txt = f"{fmt_durasi(elapsed)} / {fmt_durasi(duration)}"
        if bar:
            progres_txt += f"\n{bar}"
    else:
        progres_txt = f"Durasi: {fmt_durasi(duration)}"
    embed.add_field(name="Progress", value=progres_txt, inline=False)

    footer = f"Antrean: {len(queue_now)} lagu"
    if state.is_shuffle.get(guild_id, False):
        footer += " • Shuffle nyala"
    embed.set_footer(text=footer)

    if cover_url:
        embed.set_thumbnail(url=cover_url)
    return embed

# command-command muter lagu ngumpul di file ini
def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def play(ctx, *, nama_file: str):
        voice_client = ctx.voice_client
        if not voice_client:
            await ctx.send("Botnya gada di dalem, pake !join")
            return
        
        guild_id = ctx.guild.id
        player.cancel_idle_leave(guild_id)

        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            
        file_rel_path = _path_langsung(nama_file)
        if not file_rel_path:
            file_rel_path = music_cache.cari_file_cocok(nama_file)  # dibikin dua langkah biar gampang diliat pas nyangkut

        # kalau file lokal ga ketemu, baru kasih saran
        if not file_rel_path:
            hasil_saran = music_cache.cari_lagu(nama_file)
            if hasil_saran:
                saran = "\n".join([f"-{os.path.basename(f)}" for f in hasil_saran[:20]])
                await ctx.send(f"Blom gw tambahin jir {nama_file}, yang ini kah?\n{saran}\n\natau coba cari di youtube?: ketik: !yt {nama_file}")
            else:
                await ctx.send(f"Blom gw tambahin jir {nama_file}, coba cari di youtube?: ketik: !yt {nama_file} ")
                return
            
        file_path_full = config.music_root_dir() / file_rel_path
        if not file_path_full.exists():
            await ctx.send("Musiknya corrupt atau hilang jir")
            return

        kunci = str(file_path_full)

        # metadata sama cover dibaca sekali terus dicache
        if kunci in state.metadata_cache:
            metdat = state.metadata_cache[kunci]
        else:
            metdat = get_audio_metadata(file_path_full)
            if metdat:
                state.metadata_cache[kunci] = metdat
                
        if not metdat:
            await ctx.send("gagal baca metadata")
            return
        
        durasi = metdat["duration"]
        menit = durasi // 60
        detik = durasi % 60
        title = (metdat["title"])                         
        artist = metdat["artist"]                       
        album = metdat["album"]     

        is_playing_now = voice_client.is_playing() or voice_client.is_paused() or guild_id in state.current_playing

        # kalau lagi ada yang muter, item baru masuk antrean
        if is_playing_now:
            state.queue_asli[guild_id].append(file_rel_path)
            state.play_queue[guild_id].append(file_rel_path)
            posisi = len(state.queue_asli[guild_id])
            save_queue(guild_id)

            embed = discord.Embed(title=title, description=f"oleh {artist}\nAlbum: {album}", color=0x41639b)                                                           
            embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}", inline=True)   
            embed.add_field(name="Posisi", value=str(posisi), inline=True)
            cover_url = await cover_cache.resolve_cover(file_rel_path)
            if cover_url:
                embed.set_thumbnail(url=cover_url)
            await ctx.send(embed=embed)
            return

        player.ensure_deques(guild_id)
         
        try:
            # kalau bot lagi kosong, file lokal langsung puter
            state.current_playing[guild_id] = file_rel_path
            volume = state.tingkat_suara.get(guild_id, 0.5)
            source = player.build_audio(str(file_path_full), volume=volume)
            voice_client.play(source, after=partial(player.after_play, guild_id, voice_client))
            state.started_at[guild_id] = time.time()
            state.paused_at.pop(guild_id, None)
            state.total_pause[guild_id] = 0
            player.catat_selera(guild_id, file_rel_path)
            save_queue(guild_id)
    
            state.np_channel[guild_id] = ctx.channel.id
            embed = await create_embed_np(guild_id)
            await player.update_dashboard(ctx.channel, embed)

        except Exception as e:
            state.current_playing.pop(guild_id, None)
            await ctx.send(f"error anjay {e}")
            print(traceback.format_exc())

    @bot.command()
    async def yt(ctx, *, query: str):
        # cari youtube terus siapin item queue/now playing
        voice_client = ctx.voice_client
        if not voice_client:
            await ctx.send("Botnya gada di dalem, pake !join")
            return        
        guild_id = ctx.guild.id
        player.cancel_idle_leave(guild_id)
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
        await ctx.send(f"cariin di yt bentar: {query}...")
        try:
            data = await get_audio_source(f"ytsearch:{query}")
        except Exception as e:
            await ctx.send(f"gagal cari di yt: {e}")
            return
        
        if not data or not data.get("webpage_url"):
            await ctx.send("yt error: ga nemu hasilnya")
            return
        
        yt_item = {
            "webpage_url": data["webpage_url"],
            "title": data ["title"],
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader"),
            "duration": data.get("duration"),
            }       
        stream_url = data["url"]
        title = data["title"]
        volume = state.tingkat_suara.get(guild_id, 0.5)
        source = player.build_audio(stream_url, volume=volume)

        # kalau lagi muter sesuatu, hasil yt diselipin ke queue
        if voice_client.is_playing() or voice_client.is_paused():
            player.ensure_deques(guild_id)
            state.queue_asli[guild_id].append(yt_item)
            state.play_queue[guild_id].append(yt_item)
            save_queue(guild_id)
            embed = discord.Embed(title=f"Masuk antiran", description=yt_item["title"], color=0x12d3d3)
            if yt_item.get("thumbnail"):
                embed.set_thumbnail(url=yt_item["thumbnail"])
            if yt_item.get("duration"):
                durasi = yt_item["duration"]
                menit = durasi // 60
                detik = durasi % 60
                embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}") 
            if yt_item.get("webpage_url"):
                embed.add_field(name="Link", value=yt_item["webpage_url"], inline=False)
            await ctx.send(embed=embed)
            
        else:
            # kalau kosong ya gas langsung
            voice_client.play(source, after=partial(player.after_play, guild_id, voice_client))
            state.started_at[guild_id] = time.time()
            state.paused_at.pop(guild_id, None)
            state.total_pause[guild_id] = 0
            state.current_playing[guild_id] = yt_item
            save_queue(guild_id)
            embed = discord.Embed(title=yt_item["title"], description = f"oleh {yt_item.get('uploader', 'unknown')}", color=0x12d3d3)

            if yt_item.get("thumbnail"):
                embed.set_thumbnail(url=yt_item["thumbnail"])
            if yt_item.get("duration"):
                durasi = yt_item["duration"]
                menit = durasi // 60
                detik = durasi % 60
                embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}") 
            if yt_item.get("webpage_url"):
                embed.add_field(name="Link", value=yt_item["webpage_url"], inline=False)
            await ctx.send(embed=embed)

    @bot.command()
    async def search(ctx, *, query: str):
        # search nama lagu dari cache lokal
        hasil = music_cache.cari_lagu(query)
        if not hasil:
            await ctx.send("Blom gw tambahin jir musiknya")
            return
        format_baris = []
        for i, file_path in enumerate(hasil[:20]):
            nama_file = os.path.basename(file_path)
            folder = os.path.dirname(file_path)
            album = folder.split("/")[-1] if "/" in folder else "Unknown Album"
            nama_file = re.sub(r"^\d+\.\s*", "", nama_file)
            format_baris.append(f"{i+1}. {nama_file} [{album}]")

        state.last_search[ctx.author.id] = hasil[:20]
        formatted = "\n".join(format_baris)
        await ctx.send(f"nih ya embut '{query}':\n{formatted}")

    @bot.command()
    async def pick(ctx, nomor: int):
        # ambil salah satu hasil search terus lempar ke play
        hasil = state.last_search.get(ctx.author.id)

        if not hasil:
            await ctx.send("lu blom search apa-apa")
            return
        if nomor < 1 or nomor > len(hasil):
            await ctx.send("nomornya gabener")
            return
        
        file_rel_path = hasil[nomor - 1]
        await ctx.invoke(bot.get_command("play"), nama_file=file_rel_path)

    @bot.command()
    async def refresh(ctx):
        # paksa bangun ulang cache file + metadata sampul
        state.file_cache = music_cache.buat_music_cache()
        state.metadata_cache.clear()
        state.cover_cache.clear()
        state.cache_timestamp = time.time()
        await ctx.send(f"cache nya lu update nih: {len(state.file_cache)} entries lu mbut")

    @bot.command()
    async def pause(ctx):
        # nahan playback sementara
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await ctx.send("mengheningkan cipta bentar")
        else:
            await ctx.send("tuli kah? gada musiknya")

    @bot.command()
    async def resume(ctx):
        # lanjut lagi kalau tadi sempet dipause
        async with player.kunci_lagu(ctx.guild.id):
            guild_id = ctx.guild.id
            voice_client = ctx.voice_client
            paused = state.paused_at.pop(guild_id, None)
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await ctx.send("infokan penglanjutan musik")
            else:
                await ctx.send("tuli kah? gada musik yg berhenti")

            if paused:
                state.total_pause[guild_id] = state.total_pause.get (guild_id, 0) + (time.time() - paused)

    @bot.command()
    async def now(ctx):
        guild_id = ctx.guild.id
        embed = await create_embed_np(guild_id)

        if embed is None:
            await ctx.send("tuli kah? gada musiknya")
            return

        state.np_channel[guild_id] = ctx.channel.id
        await player.update_dashboard(ctx.channel, embed)
        
    @bot.command()
    async def next(ctx):
        # paksa loncat ke item berikutnya
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if not voice_client or not voice_client.is_connected():
                state.current_playing.pop(guild_id, None)
                state.queue_asli.pop(guild_id, None)
                state.play_queue.pop(guild_id, None)
                await ctx.send("Botnya gada di dalem, pake !join")
                return
            if not voice_client.is_playing() and not voice_client.is_paused():
                await ctx.send("tuli kah? gada musiknya")
                return
        voice_client.stop()
        await ctx.send("skip dah ke lagu berikutnya")

    @bot.command()
    async def volume(ctx, level: int):
        # volume disimpen per guild
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if 0 <= level <= 100:
                state.tingkat_suara[guild_id] = level / 100
                await ctx.send(f"volume lu di atur di {level}")
            else:
                await ctx.send("atur volume sampe 0-100 dongok")

    @bot.command()
    async def repeat(ctx):
        # toggle repeat lagu sekarang
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            baru = not state.ulang_lagu.get(guild_id, False)
            state.ulang_lagu[guild_id] = baru
            await ctx.send(f"repeat nya lagi: {'nyala' if baru else 'mati'}")
