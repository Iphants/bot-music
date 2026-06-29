from __future__ import annotations
import re
import time
import asyncio
import discord
from .metadata import get_audio_metadata
from . import state
from pathlib import Path
from . import config

_RE_WAKTU = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
_RE_OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\]", re.IGNORECASE)
_RE_META = re.compile(r"^\[[a-zA-Z]+:.*\]$")

# cari file .lrc dengan nama sama persis di sebelah file audio lokal
def _cari_lrc(audio_full_path: Path) -> Path | None:
    lrc = audio_full_path.with_suffix(".lrc")
    return lrc if lrc.is_file() else None

# ubah timestamp LRC [mm:ss.xx] jadi detik float buat sync playback
def _stamp_ke_detik(s) -> float:
    menit = int(s.group(1))
    detik = int(s.group(2))
    frac = s.group(3) or "0"
    pecahan = int(frac) / 1000 if len(frac) == 3 else int(frac) / 100
    return menit * 60 + detik + pecahan

# parse LRC bertimestamp, termasuk offset dan baris terjemahan di bawahnya
def _parse_synced(teks: str):
    offset_ms = 0
    m = _RE_OFFSET.search(teks)
    if m:
        try:
            offset_ms = int(m.group(1))
        except ValueError:
            offset_ms = 0

    entri = []
    terakhir = []  

    for raw in teks.splitlines():
        stamps = list(_RE_WAKTU.finditer(raw))
        if stamps:
            utama = _RE_WAKTU.sub("", raw).strip()
            baru = []
            for s in stamps:
                t = _stamp_ke_detik(s) - offset_ms / 1000
                e = [t, utama, []]
                entri.append(e)
                baru.append(e)
            terakhir = baru
        else:
            txt = raw.strip()
            if not txt:
                terakhir = []  
                continue
            if _RE_META.match(txt):
                continue
            for e in terakhir:
                e[2].append(txt)

    entri.sort(key=lambda x: x[0])
    return entri


# API utama lirik lokal, dipakai !lirik/!lyrics dan live lyrics
def muat_lirik(audio_rel_path: str):
    full = config.music_root_dir() / audio_rel_path
    lrc = _cari_lrc(full)
    if not lrc:
        return None
    try:
        teks = lrc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if _RE_WAKTU.search(teks):
        entri = _parse_synced(teks)
        return ("synced", entri) if entri else None

    baris = [b.strip() for b in teks.splitlines() if b.strip() and not _RE_META.match(b.strip())]
    return ("polos", baris) if baris else None

# ambil jendela kecil lirik synced sekitar posisi lagu sekarang
def potong_synced(entri, elapsed, sebelum=1, sesudah=3):
    if not entri:
        return [], -1
    idx = -1
    for i, e in enumerate(entri):
        if e[0] <= elapsed:
            idx = i
        else:
            break
    if idx < 0:
        return entri[: sebelum + sesudah + 1], -1
    mulai = max(0, idx - sebelum)
    selesai = min(len(entri), idx + sesudah + 1)
    return entri[mulai:selesai], idx - mulai

# ambil jendela lirik polos dengan tebakan posisi dari rasio durasi
def potong_polos(baris, elapsed, duration, sebelum=1, sesudah=3):
    if not baris:
        return [], -1
    if duration and duration > 0:
        rasio = min(1.0, max(0.0, elapsed / duration))
        idx = min(len(baris) - 1, int(rasio * len(baris)))
    else:
        idx = 0
    mulai = max(0, idx - sebelum)
    selesai = min(len(baris), idx + sesudah + 1)
    return baris[mulai:selesai], idx - mulai

POL_GAP = 0.5
MIN_GAP = 2.0

# hitung posisi lagu yang konsisten dengan pause/resume state player
def _elapsed(guild_id):
    mulai = state.started_at.get(guild_id)
    if not mulai:
        return None
    ttl = state.total_pause.get(guild_id, 0)
    if guild_id in state.paused_at:
        return max(0, state.paused_at[guild_id] - mulai - ttl)
    return max(0, time.time() - mulai - ttl)

# bikin identitas track supaya live lyrics tahu kapan lagu berganti
def _track_id(currnet):
    if currnet is None:
        return None
    if isinstance(currnet, dict):
        return currnet.get("webpage_url")
    return str(currnet)

# load data lirik untuk track aktif; YT sengaja ditandai tanpa lirik lokal
def _muat_live(current):
    if isinstance(current, dict):
        return "yt", None, None
    file_rel = str(current)
    hasil = muat_lirik  (file_rel)
    full = config.music_root_dir() / file_rel
    metdat = state.metadata_cache.get(str(full)) or get_audio_metadata(full)
    duration = metdat.get("duration") if metdat else None
    if not hasil:
        return "none", None, duration
    jenis, data = hasil
    return jenis, data, duration

# cari index baris aktif supaya panel live cuma diedit saat berubah
def _idx_aktif(jenis, data, duration, elapsed):
    if jenis == "synced" and data:
        idx = -1
        for i, e in enumerate(data):
            if e[0] <= elapsed:
                idx = i
            else:
                break
        return idx
    if jenis == "polos" and data:
        if duration and duration > 0:
            rasio = min(1.0, max(0.0, elapsed/duration))
            return min(len(data) - 1, int(rasio * len(data)))
        return 0
    return -1

# render teks panel live lyrics sebelum dikirim/diedit ke Discord
def _render(jenis, data, duration, elapsed):
    if jenis == "yt":
        return "Lagu yt ga ada lirik lokal"
    if jenis == "none" or not data:
        return "Lirik ga ketemu buat lagu ini"
    if jenis == "synced":
        pot, idx = potong_synced(data, elapsed)
        out = ["**Live Lyrics**"]
        for i, (t, utama, subs) in enumerate(pot):
            u = utama or "♪"
            out.append(f"**> {u}**" if i == idx else u)
            for s in subs:
                out.append(f"-# {s}")
        return "\n".join(out)
    
    pot, idx = potong_polos(data, elapsed, duration)
    out = ["**Live Lyrics**", "-# (lirik gada timestamp, nebak dari durasi)"]
    for i, b in enumerate(pot):
        out.append(f"**> {b}**" if i == idx else b)
    return "\n".join(out)

# edit satu pesan live lyrics, dibatasi MIN_GAP biar ga spam API Discord
async def _coba_edit(ch, sesi, teks, idx):
    now = time.time()
    if teks == sesi["last_render"]:
        sesi["last_idx"] = idx
        return
    if sesi["message_id"] and (now - sesi["last_edit"]) < MIN_GAP:
        return
    try:
        if sesi["message_id"] is None:
            msg = await ch.send(teks)
            sesi["message_id"] = msg.id
        else:
            msg = await ch.fetch_message(sesi["message_id"])
            await msg.edit(content=teks)
    except discord.NotFound:
        try:
            msg = await ch.send(teks)
            sesi["message_id"] = msg.id
        except discord.HTTPException as e:
            print(f"[LIRIK] gagal kirim ulang: {e}")
            return
    except discord.HTTPException as e:
        print(f"[LIRIK]gagal edit: {e}")
        return
    sesi["last_edit"] = now
    sesi["last_idx"] = idx
    sesi["last_render"] = teks

# loop per guild untuk ngikutin lagu aktif dan update panel live lyrics
async def _loop_live(bot, guild_id):
    sesi = state.lirik_sesi.get(guild_id)
    if not sesi:
        return
    ch = bot.get_channel(sesi["channel_id"])
    if not ch:
        state.lirik_sesi.pop(guild_id, None)
        return
    try:
        while True:
            sesi = state.lirik_sesi.get(guild_id)
            if not sesi:
                return
            
            current = state.current_playing.get(guild_id)
            track = _track_id(current)
            if track != sesi["track"]:
                sesi["track"] = track
                sesi["last_idx"] = -999
                if current is None:
                    sesi["jenis"], sesi["data"], sesi["duration"] = "none", None, None
                else:
                    sesi["jenis"], sesi["data"], sesi["duration"] = _muat_live(current)

            if current is None:
                await _coba_edit(ch, sesi, "gada lagu yang diputer", -1)
                await asyncio.sleep(POL_GAP)
                continue

            elapsed = _elapsed(guild_id) or 0
            idx = _idx_aktif(sesi["jenis"], sesi["data"], sesi["duration"], elapsed)
            if idx != sesi["last_idx"]:
                teks = _render(sesi["jenis"], sesi["data"], sesi["duration"], elapsed)
                await _coba_edit(ch, sesi, teks, idx)

            await asyncio.sleep(POL_GAP)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[LIRIK] loop error: {e}")

# dipanggil command !lirik live untuk mulai satu sesi live lyrics per guild
async def start_live(bot, guild_id, channel):
    await stop_live(bot, guild_id)
    sesi = {
        "channel_id": channel.id,
        "message_id": None,
        "last_idx": -999,
        "last_edit": 0.0,
        "last_render": "",
        "track": None,
        "jenis": None,
        "data": None,
        "duration": None,
        "task": None,
    }
    state.lirik_sesi[guild_id] = sesi
    sesi["task"] = asyncio.create_task(_loop_live(bot, guild_id))

# dipanggil command !lirik off dan start_live buat matiin sesi lama
async def stop_live(bot, guild_id):
    sesi = state.lirik_sesi.pop(guild_id, None)
    if not sesi:
        return False
    task = sesi.get("task")
    if task and not task.done():
        task.cancel()
    msg_id = sesi.get("message_id")
    ch = bot.get_channel(sesi.get("channel_id")) if sesi.get("channel_id") else None
    if msg_id and ch:
        try:
            msg = await ch.fetch_message(msg_id)
            await msg.edit(content="live lyrics mati")
        except (discord.NotFound, discord.HTTPException):
            pass
    return True
