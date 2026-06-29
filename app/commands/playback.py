from __future__ import annotations
import os
import time
import traceback
import discord
import io
import re
import asyncio
import requests
from pathlib import Path
from discord.ext import commands
from .. import checks
from .. import config
from .. import music_cache
from .. import player
from .. import state
from ..yt import get_audio_source
from functools import partial
from ..metadata import get_audio_metadata, get_cover
from ..autoalir_store import save_queue
from .. import cover_cache
from .. import lyrics as lyr


_RAW = ("raw", "download", "original", "asli")
MAX_QUEUE = 100
MAX_YT_QUERY = 200


def _nama_cover(cover: bytes) -> str:
    if cover.startswith(b"\x89PNG\r\n\x1a\n"):
        return "cover.png"
    return "cover.jpg"


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

    embed = discord.Embed(
        title="lagi play",
        description=desc,
        color=0x41639B,
    )
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


def _detect_ext(b: bytes) -> str:
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if b.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return "jpg"


def _sanitize_nama(nama: str) -> str:
    nama = re.sub(r'[/\\:*?"<>|]', "", str(nama)).strip()
    return nama[:100] or "cover"


def _fetch_url(url: str):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception as e:
        print(f"[THUMBNAIL] gagal fetch YT thumb: {e}")
    return None


def _compress_preview(raw_bytes: bytes):
    from PIL import Image

    img = Image.open(io.BytesIO(raw_bytes))
    img.thumbnail((800, 800))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


async def _lirik_oneshot(ctx, guild_id):
    current = state.current_playing.get(guild_id)
    if not current:
        await ctx.send("gada lagu yang diputer")
        return
    if isinstance(current, dict):
        await ctx.send("Lagu YT gada lirik lokal")
        return
    file_rel = str(current)
    hasil = lyr.muat_lirik(file_rel)
    if not hasil:
        await ctx.send("Lirik ga ketemu buat lagu ini")
        return
    jenis, data = hasil
    elapsed = elaps_lagu(guild_id) or 0
    if jenis == "synced":
        pot, idx_on = lyr.potong_synced(data, elapsed)
        out = []
        for i, (t, utama, subs) in enumerate(pot):
            u = utama or "♪"
            out.append(f"**> {u}**" if i == idx_on else u)
            for s in subs:
                out.append(f"-# {s}")
        await ctx.send("\n".join(out))
    else:
        full = config.music_root_dir() / file_rel
        metdat = state.metadata_cache.get(str(full)) or get_audio_metadata(full)
        duration = metdat.get("duration") if metdat else None
        pot, idx_on = lyr.potong_polos(data, elapsed, duration)
        out = ["-# (lirik ga ada timestamp, nebak dari durasi)"]
        for i, b in enumerate(pot):
            out.append(f"**> {b}**" if i == idx_on else b)
        await ctx.send("\n".join(out))


def setup(bot: commands.Bot) -> None:
    @bot.command()
    @commands.cooldown(2, 5, commands.BucketType.user)
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
            file_rel_path = music_cache.cari_file_cocok(nama_file)

        if not file_rel_path:
            hasil_saran = music_cache.cari_lagu(nama_file)
            if hasil_saran:
                saran = "\n".join([f"-{os.path.basename(f)}" for f in hasil_saran[:20]])
                await ctx.send(
                    f"Blom gw tambahin jir {nama_file}, yang ini kah?\n"
                    f"{saran}\n\n"
                    f"atau coba cari di youtube?: ketik: !yt {nama_file}"
                )
                return

            await ctx.send(
                f"Blom gw tambahin jir {nama_file}, "
                f"coba cari di youtube?: ketik: !yt {nama_file}"
            )
            return
        file_path_full = config.music_root_dir() / file_rel_path
        if not file_path_full.exists():
            await ctx.send("Musiknya corrupt atau hilang jir")
            return

        kunci = str(file_path_full)

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
        title = metdat["title"]
        artist = metdat["artist"]
        album = metdat["album"]

        is_playing_now = (
            voice_client.is_playing()
            or voice_client.is_paused()
            or guild_id in state.current_playing
        )

        if is_playing_now:
            if len(state.play_queue.get(guild_id, [])) >= MAX_QUEUE:
                await ctx.send(f"antrean dh penuh ({MAX_QUEUE} lagu), tunggu abis dulu")
                return
            state.queue_asli[guild_id].append(file_rel_path)
            state.play_queue[guild_id].append(file_rel_path)
            posisi = len(state.queue_asli[guild_id])
            save_queue(guild_id)

            embed = discord.Embed(
                title=title,
                description=f"oleh {artist}\nAlbum: {album}",
                color=0x41639B,
            )
            embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}", inline=True)
            embed.add_field(name="Posisi", value=str(posisi), inline=True)
            cover_url = await cover_cache.resolve_cover(file_rel_path)
            if cover_url:
                embed.set_thumbnail(url=cover_url)
            await ctx.send(embed=embed)
            return

        player.ensure_deques(guild_id)
        try:
            state.current_playing[guild_id] = file_rel_path
            volume = state.tingkat_suara.get(guild_id, 0.5)
            source = player.build_audio(str(file_path_full), volume=volume)
            voice_client.play(
                source, after=partial(player.after_play, guild_id, voice_client)
            )
            state.started_at[guild_id] = time.time()
            state.paused_at.pop(guild_id, None)
            state.total_pause[guild_id] = 0
            player.catat_selera(guild_id, file_rel_path)
            save_queue(guild_id)
            state.np_channel[guild_id] = ctx.channel.id
            embed = await create_embed_np(guild_id)
            await player.update_dashboard(ctx.channel, embed)

        except Exception:
            state.current_playing.pop(guild_id, None)
            await ctx.send("error internal pas mau play, coba lagi / lapor admin")
            print(traceback.format_exc())

    @bot.command()
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def yt(ctx, *, query: str):
        voice_client = ctx.voice_client
        if not voice_client:
            await ctx.send("Botnya gada di dalem, pake !join")
            return

        guild_id = ctx.guild.id
        if len(query) > MAX_YT_QUERY:
            await ctx.send("query yt udah kepanjangan, singkatin dong")
            return

        if (voice_client.is_playing() or voice_client.is_paused()) and len(
            state.play_queue.get(guild_id, [])
        ) >= MAX_QUEUE:
            await ctx.send(f"antrean udah penuh ({MAX_QUEUE} lagu)")
            return

        player.cancel_idle_leave(guild_id)
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
        await ctx.send(f"cariin di yt bentar: {query}...")
        try:
            data = await get_audio_source(f"ytsearch:{query}")
        except Exception as e:
            await ctx.send("gagal cari di yt, coba lagi / lapor admin")
            print(f"[YT ERROR] {e}")
            print(traceback.format_exc())
            return
        if not data or not data.get("webpage_url"):
            await ctx.send("yt error: ga nemu hasilnya")
            return

        yt_item = {
            "webpage_url": data["webpage_url"],
            "title": data["title"],
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader"),
            "duration": data.get("duration"),
        }
        if voice_client.is_playing() or voice_client.is_paused():
            player.ensure_deques(guild_id)
            if len(state.play_queue.get(guild_id, [])) >= MAX_QUEUE:
                await ctx.send(f"antrean udah penuh ({MAX_QUEUE} lagu)")
                return
            state.queue_asli[guild_id].append(yt_item)
            state.play_queue[guild_id].append(yt_item)
            save_queue(guild_id)

            embed = discord.Embed(
                title="Masuk antrean",
                description=yt_item["title"],
                color=0x12D3D3,
            )
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
            return

        try:
            stream_url = data["url"]
            volume = state.tingkat_suara.get(guild_id, 0.5)
            source = player.build_audio(stream_url, volume=volume)

            state.current_playing[guild_id] = yt_item
            voice_client.play(
                source, after=partial(player.after_play, guild_id, voice_client)
            )
            state.started_at[guild_id] = time.time()
            state.paused_at.pop(guild_id, None)
            state.total_pause[guild_id] = 0
            save_queue(guild_id)

            embed = discord.Embed(
                title=yt_item["title"],
                description=f"oleh {yt_item.get('uploader', 'unknown')}",
                color=0x12D3D3,
            )

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

        except Exception as e:
            state.current_playing.pop(guild_id, None)
            await ctx.send("error internal pas mau play yt, coba lagi / lapor admin")
            print(f"[YT PLAY ERROR] {e}")
            print(traceback.format_exc())

    @bot.command()
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def thumbnail(ctx, *, arg: str = ""):
        guild_id = ctx.guild.id
        loop = asyncio.get_running_loop()
        mode = "preview"
        nama_lagu = ""
        arg = arg.strip()
        if arg:
            tokens = arg.split(maxsplit=1)
            if tokens[0].lower() in _RAW:
                mode = "raw"
                nama_lagu = tokens[1].strip() if len(tokens) > 1 else ""
            else:
                nama_lagu = arg

        if nama_lagu:
            file_rel = _path_langsung(nama_lagu) or music_cache.cari_file_cocok(
                nama_lagu
            )
            if not file_rel:
                await ctx.send(f"ga nemu lagu '{nama_lagu}' di lokal")
                return
            target = file_rel
        else:
            target = state.current_playing.get(guild_id)
            if not target:
                await ctx.send("gada lagu yang lagi diputer")
                return
        if isinstance(target, dict):
            thumb_url = target.get("thumbnail")
            if not thumb_url:
                await ctx.send("lagu YT ini ga ada thumbnail")
                return
            raw = await loop.run_in_executor(None, _fetch_url, thumb_url)
            if not raw:
                await ctx.send("gagal ambil thumbnail YT, ambil manual aja")
                return
            title = target.get("title", "cover")
            artist = target.get("uploader")
            ext = "jpg"
        else:
            file_rel = str(target)
            full = config.music_root_dir() / file_rel
            if not full.exists():
                await ctx.send("file lagunya udah gada di disk")
                return
            raw = await loop.run_in_executor(None, get_cover, full)
            if not raw:
                await ctx.send("lagu ini gada cover art")
                return
            ext = _detect_ext(raw)
            metdat = state.metadata_cache.get(str(full)) or get_audio_metadata(full)
            if metdat:
                title = metdat.get("title") or os.path.basename(file_rel)
                artist = metdat.get("artist")
            else:
                title = os.path.basename(file_rel)
                artist = None

        if artist and artist != "Unknown":
            base_nama = _sanitize_nama(f"{artist} - {title}")
        else:
            base_nama = _sanitize_nama(title)

        try:
            if mode == "raw":
                size_kb = len(raw) // 1024
                fname = f"{base_nama}.{ext}"
                file = discord.File(fp=io.BytesIO(raw), filename=fname)
                await ctx.send(
                    f"cover asli ({ext.upper()}, {size_kb}KB: {title})", file=file
                )
            else:
                try:
                    comp = await loop.run_in_executor(None, _compress_preview, raw)
                except Exception as e:
                    print(f"[THUMBNAIL] kompresi gagal, fallback raw: {e}")
                    comp = raw
                size_kb = len(comp) // 1024
                fname = f"{base_nama}_preview.jpg"
                file = discord.File(fp=io.BytesIO(comp), filename=fname)
                await ctx.send(f"cover preview ({size_kb}KB: {title})", file=file)
        except discord.HTTPException as e:
            await ctx.send("gagal kirim cover (mungkin kegedean)")
            print(f"[THUMBNAIL] gagal kirim: {e}")

    @bot.command()
    @commands.cooldown(2, 5, commands.BucketType.user)
    async def search(ctx, *, query: str):
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
            format_baris.append(f"{i + 1}. {nama_file} [{album}]")

        state.last_search[ctx.author.id] = hasil[:20]
        formatted = "\n".join(format_baris)
        await ctx.send(f"nih ya embut '{query}':\n{formatted}")

    @bot.command()
    @commands.cooldown(2, 5, commands.BucketType.user)
    async def pick(ctx, nomor: int):
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
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @checks.is_dj_or_admin()
    async def refresh(ctx):
        state.file_cache = music_cache.buat_music_cache()
        state.metadata_cache.clear()
        state.cover_cache.clear()
        state.cache_timestamp = time.time()
        await ctx.send(
            f"cache nya lu update nih: {len(state.file_cache)} entries lu mbut"
        )

    @bot.command()
    async def pause(ctx):
        guild_id = ctx.guild.id
        voice_client = ctx.voice_client

        if voice_client and voice_client.is_playing():
            voice_client.pause()
            state.paused_at[guild_id] = time.time()
            await ctx.send("mengheningkan cipta bentar")
        else:
            await ctx.send("tuli kah? gada musiknya")

    @bot.command()
    async def resume(ctx):
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
                state.total_pause[guild_id] = state.total_pause.get(guild_id, 0) + (
                    time.time() - paused
                )

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
    async def lyrics(ctx):
        await _lirik_oneshot(ctx, ctx.guild.id)

    @bot.command()
    @commands.cooldown(2, 6, commands.BucketType.user)
    async def lirik(ctx, *, arg: str = ""):
        guild_id = ctx.guild.id
        arg = arg.strip().lower()
        if arg in ("off", "mati", "stop"):
            ok = await lyr.stop_live(bot, guild_id)
            await ctx.send(
                "live lyrics dimatiin" if ok else "Live lyrics emang ga aktif"
            )
            return
        if arg in ("live", "on"):
            if state.current_playing.get(guild_id) is None:
                await ctx.send("gada lagu yang lagi diputer")
                return

            if guild_id in state.lirik_sesi:
                await ctx.send("live lyrics udah aktif kok")
                return
            await lyr.start_live(bot, guild_id, ctx.channel)
            await ctx.send("Live lyrics nyala, panel bakal gw update sendiri")
            return
        await _lirik_oneshot(ctx, guild_id)

    @bot.command()
    async def next(ctx):
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
    @checks.is_dj_or_admin()
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
