from __future__ import annotations
import asyncio
import os
import random
import re
import time
import discord
from collections import Counter, deque
from functools import partial
from pathlib import Path
from random import shuffle as sf
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from . import config
from . import runtime
from . import state
from .yt import get_audio_source
from .autoalir_store import save_autoalir_state, save_queue

# helper kecil buat ngunci guild dan beresin queue
def kunci_lagu(guild_id):
    if guild_id not in state.kunci_guild:
        state.kunci_guild[guild_id] = asyncio.Lock()
    return state.kunci_guild[guild_id]

def shuffle_queue(guild_id):
    q = state.play_queue.get(guild_id)
    if not q or len(q) <= 1:
        return
    
    temp = list(q)
    random.shuffle(temp)
    state.play_queue[guild_id] = deque (temp)

def shuffle_internal(guild_id):
    q = list(state.play_queue[guild_id])
    if len(q) <= 1:
        return
    kepala = q[0]
    ekor = q[1:]
    random.shuffle(ekor)
    state.play_queue[guild_id] = deque([kepala] + ekor)

def ensure_deques(guild_id):
    if guild_id not in state.queue_asli:
        state.queue_asli[guild_id] = deque()
    if guild_id not in state.play_queue:
        state.play_queue[guild_id] = deque()

def debug_autoalir(*args):
    if getattr(state, "debug_autoalir", False):
        print("[AUTOALIR DEBUG]", *args)

# batas history autoalir yang agak panjang
RIWAYAT_AUTOALIR_MID = 18

def catat_selera(guild_id, item):
    if not isinstance(item, str):
        return
    if guild_id not in state.selera_guild:
        state.selera_guild[guild_id] = {}
    state.selera_guild[guild_id][item] = state.selera_guild[guild_id].get(item, 0) + 1
    state.lagu_terakhir_lokal[guild_id] = item
    if guild_id not in state.history_autoalir:
        state.history_autoalir[guild_id] = deque(maxlen=7)
    state.history_autoalir[guild_id].append(item)
    if guild_id not in state.history_mid_autoalir:
        state.history_mid_autoalir[guild_id] = deque(maxlen=RIWAYAT_AUTOALIR_MID)
    state.history_mid_autoalir[guild_id].append(item)
    judul = judul_dasar(item)
    if guild_id not in state.history_jdul_autoalir:
        state.history_jdul_autoalir[guild_id] = deque(maxlen=6)
    state.history_jdul_autoalir[guild_id].append(judul)

    debug_autoalir(f"catat_selera guild={guild_id}", f"item={item}", f"judul_dasar={judul}", f"jumlah_putar={state.selera_guild[guild_id][item]}", f"riwayat_file={list(state.history_autoalir[guild_id])}", f"riwayat_mid={list(state.history_mid_autoalir[guild_id])}", f"riwayat_judul={list(state.history_jdul_autoalir[guild_id])}", )
    save_autoalir_state()

# pecah rel path lagu biar gampang dibandingin folder/artist/album
_RE_DISC = re.compile(r"^(?:cd|dis[ck])\s*\d+$")

def _disc_folder(nama: str) -> bool:
    return bool(_RE_DISC.match(nama.strip().lower()))

def pecah_struktur_lagu(rel_path: str):
    rel_norm = str(rel_path).replace("\\", "/").strip("/")
    p = Path(rel_norm)
    folders = list(p.parts[:-1])
    n = len(folders)
    hasil = {"rel": rel_norm, "parent": str(p.parent).replace("\\", "/").lower(), "top": None, "unit": None, "artist": None, "album": None, "disc": None, "nama_file": p.name.lower(),}

    if n == 0:
        debug_autoalir(f"pecah_struktur: {rel_norm} -> {hasil}")
        return hasil
    
    album_idx = n - 1
    if _disc_folder(folders[-1]):
        hasil["disc"] = folders[-1].lower()
        album_idx = n - 2

    hasil["top"] = folders[0].lower()
    if album_idx >= 0:
        hasil["album"] = folders[album_idx].lower()

    if album_idx > 1:
        hasil["unit"] = folders[1].lower()

    hasil["artist"] = hasil["unit"] or hasil["top"]
    
    debug_autoalir(f"pecah_struktur: {rel_norm} -> {hasil}")
    return hasil

# nebak ini lagu utama, ost, atau cuma varian file
def tipe_lagu(rel_path: str, info=None):
    info = info or pecah_struktur_lagu(rel_path)
    path_txt = str(rel_path).replace("\\", "/").lower()
    nama = info["nama_file"]

    kata_ost = {"ost", "original soundtrack", "soundtrack", "bgm","score","backing track", }
    kata_varian_kuat = {"game size", "tv size", "anime size", "movie size", "short ver", "short version", "short size", "pv size", "off vocal", "instrumental", "karaoke", "minus one", "demo", "edit", }

    if re.search(r"(^|[/\s_\-\[\(])ost($|[/\s_\-\]\)])", path_txt):
        return "ost"
    if any(kata in path_txt for kata in kata_ost if kata != "ost"):
        return "ost"
    if any(kata in nama for kata in kata_varian_kuat):
        return "varian"
    return "utama"

# ngitung kecenderungan history sekarang numpuk ke parent/artist mana
def dom_auto(guild_id):
    hist = list(state.history_mid_autoalir.get(guild_id, []))[-RIWAYAT_AUTOALIR_MID:]
    h_parent = Counter()
    h_artist = Counter()
    h_top = Counter()

    for item in hist:
        if not isinstance(item, str):
            continue

        info = pecah_struktur_lagu(item)
        if info["parent"]:
            h_parent[info["parent"]] += 1
        if info["artist"]:
            h_artist[info["artist"]] += 1
        if info["top"]:
            h_top[info["top"]] += 1

    return {"total": len(hist), "parent": h_parent, "artist": h_artist, "top":h_top }

# kalau history udah kepenuhan, skor ditahan dikit
def penalti_dom(info, dominasi, skor, rincian):
    if dominasi["total"] < 10:
        return skor

    jumlah_parent = dominasi["parent"].get(info["parent"], 0)
    if jumlah_parent >= 7:
        penalti = min(50, (jumlah_parent - 6) * 10)
        skor -= penalti
        rincian.append(f"penalti_dominasi_parent=-{penalti}")

    artist = info["artist"]
    jumlah_artist = dominasi["artist"].get(artist, 0) if artist else 0
    if jumlah_artist >= 5:
        penalti = min(36, (jumlah_artist - 4) * 9)
        skor -= penalti
        rincian.append(f"penalti_dominasi_artist=-{penalti}")

    top = info["top"]
    if top and top != artist:
        jumlah_top = dominasi.get("top", {}).get(top, 0)
        if jumlah_top >= 12:
            penalti = min(18, (jumlah_top - 11) * 4)
            skor -= penalti
            rincian.append(f"penalti_dominasi_top=-{penalti}")
    return skor

def penalti_tipe(tipe_kandidat, tipe_terakhir, tahap, skor, rincian):
    skala = {
        "utama": {"ost": 42, "varian": 28, "varian_lanjut": 18},
        "fallback1": {"ost": 30, "varian": 20, "varian_lanjut": 12},
        "fallback2": {"ost": 18, "varian": 12, "varian_lanjut": 8},
    }[tahap]

    if tipe_kandidat == "ost" and tipe_terakhir != "ost":
        skor -= skala["ost"]
        rincian.append(f"penalti_masuk_ost=-{skala['ost']}")
    elif tipe_kandidat == "varian" and tipe_terakhir == "utama":
        skor -= skala["varian"]
        rincian.append(f"penalti_masuk_varian=-{skala['varian']}")
    elif tipe_kandidat == "varian" and tipe_terakhir == "varian":
        skor -= skala["varian_lanjut"]
        rincian.append(f"penalti_varian_lanjut=-{skala['varian_lanjut']}")
    elif tipe_kandidat == "utama" and tipe_terakhir in {"ost", "varian"}:
        skor += 8
        rincian.append("bonus_balik_lagu_utama=8")
    return skor

# inti autoalirnya, nyari kandidat lanjut yang masih nyambung
def pilih_lagu_auto(guild_id):
    terakhir = state.lagu_terakhir_lokal.get(guild_id)
    if not terakhir:
        debug_autoalir(f"guild={guild_id} gagal: lagu_terakhir_lokal kosong")
        return None

    debug_autoalir(f"mulai pilih_lagu_auto guild={guild_id}")
    debug_autoalir(f"lagu terakhir = {terakhir}")

    info_terakhir = pecah_struktur_lagu(terakhir)
    judul_terakhir = judul_dasar(terakhir)
    tipe_terakhir = tipe_lagu(terakhir, info_terakhir)
    dominasi = dom_auto(guild_id)

    riwayat_file = list(state.history_autoalir.get(guild_id, []))
    riwayat_judul = list(state.history_jdul_autoalir.get(guild_id, []))
    antrian_sekarang = []

    for item in state.play_queue.get(guild_id, []):
        if isinstance(item, str):
            tmp_item = str(item).replace("\\", "/")
            if tmp_item not in antrian_sekarang:
                antrian_sekarang.append(tmp_item)
    debug_autoalir(f"riwayat_file = {list(riwayat_file)}")
    debug_autoalir(f"riwayat_judul = {list(riwayat_judul)}")
    debug_autoalir(f"antrian sekarang = {list(antrian_sekarang)}")
    debug_autoalir(f"tipe_terakhir = {tipe_terakhir}", f"dominasi_parent = {dominasi['parent'].most_common(3)}", f"dominasi_artist = {dominasi['artist'].most_common(3)}", )

    # ngumpulin semua path unik dari cache biar ga muter key doang
    cache = state.file_cache if state.file_cache else {}
    semua_rel = []
    for daftar in cache.values():
        for item in daftar:
            rel_norm = str(item).replace("\\", "/")
            if rel_norm not in semua_rel:
                semua_rel.append(rel_norm)

    debug_autoalir(f"total kandidat mentah dari cache = {len(semua_rel)}")

    kandidat = []

    # putaran utama, ini yang paling ketat filternya
    for rel_path in semua_rel:
        if rel_path == terakhir:
            continue
        if rel_path in riwayat_file:
            continue
        if rel_path in antrian_sekarang:
            continue

        info = pecah_struktur_lagu(rel_path)
        judul_kandidat = judul_dasar(rel_path)

        skor = 0
        rincian = []

        if info["parent"] == info_terakhir["parent"]:
            skor += 120
            rincian.append("parent_sama=120")
        if info["album"] and info["album"] == info_terakhir["album"]:
            skor += 40
            rincian.append("album_sama=40")
        if info["artist"] and info["artist"] == info_terakhir["artist"]:
            skor += 70
            rincian.append("artist_sama=70")
        if info["disc"] and info["disc"] == info_terakhir["disc"]:
            skor += 20
            rincian.append("disc_sama=20")
        elif info["top"] and info["top"] == info_terakhir["top"]:
            skor += 25
            rincian.append("top_sama=25")

        nama = info["nama_file"]
        nama_terakhir = info_terakhir["nama_file"]
        tipe_kandidat = tipe_lagu(rel_path, info)

        if "game size" in nama and "game size" in nama_terakhir:
            skor -= 10
            rincian.append("penalti_game_size=-10")
        if "tv size" in nama and "tv size" in nama_terakhir:
            skor -= 10
            rincian.append("penalti_tv_size=-10")
        if "off vocal" in nama and "off vocal" in nama_terakhir:
            skor -= 12
            rincian.append("penalti_off_vocal=-12")
        if "instrumental" in nama and "instrumental" in nama_terakhir:
            skor -= 12
            rincian.append("penalti_instrumental=-12")

        # kalau judul dasarnya barusan muter, sengaja diteken
        if judul_kandidat == judul_terakhir:
            skor -= 90
            rincian.append("penalti_keluarga_judul_terakhir=-90")
        elif judul_kandidat in riwayat_judul:
            skor -= 35
            rincian.append("penalti_judul_recent=-35")

        skor = penalti_tipe(tipe_kandidat, tipe_terakhir, "utama", skor, rincian)
        skor = penalti_dom(info, dominasi, skor, rincian)

        if skor <= 0:
            continue

        kandidat.append((rel_path, skor))
        debug_autoalir(
            f"kandidat utama: {rel_path} | judul={judul_kandidat} | tipe={tipe_kandidat} | skor={skor} | rincian={rincian}"
        )

    # kalau gagal total, longgarin dikit tapi masih nyari yang searah
    if not kandidat:
        debug_autoalir("masuk fallback 1")

        for rel_path in semua_rel:
            if rel_path == terakhir:
                continue
            if rel_path in antrian_sekarang:
                continue

            info = pecah_struktur_lagu(rel_path)
            judul_kandidat = judul_dasar(rel_path)
            skor = 0
            rincian = []

            if info["parent"] == info_terakhir["parent"]:
                skor += 100
                rincian.append("parent_sama=100")
            if info["artist"] and info["artist"] == info_terakhir["artist"]:
                skor += 60
                rincian.append("artist_sama=60")
            if info["album"] and info["album"] == info_terakhir["album"]:
                skor += 30
                rincian.append("album_sama=30")
            elif info ["top"] and info ["top"] == info_terakhir["top"]:
                skor += 20
                rincian.append("top_sama=20")
            if info["disc"] and info["disc"] == info_terakhir["disc"]:
                skor += 15
                rincian.append("disc_sama=15")
            bonus_selera = min(state.selera_guild.get(guild_id, {}).get(rel_path, 0), 3) * 3
            if bonus_selera:
                skor += bonus_selera
                rincian.append(f"bonus_selera={bonus_selera}")

            if judul_kandidat == judul_terakhir:
                skor -= 60
                rincian.append("penalti_keluarga_judul_terakhir=-60")
            elif judul_kandidat in riwayat_judul:
                skor -= 25
                rincian.append("penalti_judul_recent=-25")

            tipe_kandidat = tipe_lagu(rel_path, info)
            skor = penalti_tipe(tipe_kandidat, tipe_terakhir, "fallback1", skor, rincian)
            skor = penalti_dom(info, dominasi, skor, rincian)

            if skor <= 0:
                continue

            kandidat.append((rel_path, skor))
            debug_autoalir(
                f"kandidat fallback1: {rel_path} | judul={judul_kandidat} | tipe={tipe_kandidat} | skor={skor} | rincian={rincian}"
            )

    # mentok lagi, ambil apa aja asal ga terlalu deket history/antrian
    if not kandidat:
        debug_autoalir("masuk fallback 2")

        for rel_path in semua_rel:
            if rel_path == terakhir:
                continue
            if rel_path in riwayat_file:
                continue
            if rel_path in antrian_sekarang:
                continue

            judul_kandidat = judul_dasar(rel_path)
            info = pecah_struktur_lagu(rel_path)
            tipe_kandidat = tipe_lagu(rel_path, info)

            skor = 20
            rincian = ["base_fallback2=20"]

            bonus_selera = min(state.selera_guild.get(guild_id, {}).get(rel_path, 0), 3) * 2
            if bonus_selera:
                skor += bonus_selera
                rincian.append(f"bonus_selera={bonus_selera}")
            if judul_kandidat == judul_terakhir:
                skor -= 40
                rincian.append("penalti_keluarga_judul_terakhir=-40")
            elif judul_kandidat in riwayat_judul:
                skor -= 15
                rincian.append("penalti_judul_recent=-15")

            skor = penalti_tipe(tipe_kandidat, tipe_terakhir, "fallback2", skor, rincian)
            skor = penalti_dom(info, dominasi, skor, rincian)

            if skor <= 0:
                continue

            kandidat.append((rel_path, skor))
        debug_autoalir(
            f"kandidat fallback2: {rel_path} | judul={judul_kandidat} | tipe={tipe_kandidat} | skor={skor} | rincian={rincian}"
        )

    # habis itu ambil dari kandidat atas, tapi tetep berbobot
    if not kandidat:
        debug_autoalir("gagal total: tidak ada kandidat")
        return None

    kandidat.sort(key=lambda x: x[1], reverse=True)
    kandidat_teratas = kandidat[:7]

    debug_autoalir("top kandidat =", kandidat_teratas)

    pilihan = random.choices(
        [item for item, _ in kandidat_teratas],
        weights=[skor for _, skor in kandidat_teratas],
        k=1
    )[0]

    debug_autoalir(f"pilihan akhir = {pilihan}")
    return pilihan

# nyopot embel-embel judul biar gampang dibandingin
kata_varian = {"game size", "tv size", "anime size", "movie size", "short ver", "short version", "short size", "pv size", "off vocal", "instrumental", "acoustic", "live", "remix",  "extended mix", "speed up", "sped up", "slowed down", "stripped", "a cappela", "cover", "ver.", "version", "demo", "edit",}

def judul_dasar (rel_path: str) -> str :

    nama = Path(str(rel_path).replace("\\", "/")).stem.lower()
    nama = re.sub(r"^\d+\s*[\.\-_\)\]]*\s*", "", nama)
    nama = nama.replace("_", " ")
    nama = re.sub(r"\s+", " ", nama).strip()

    def bersihin_group (match):
        teks = match.group(0).lower()
        if any (k in teks for k in kata_varian):
            return " "
        return match.group(0)
    
    nama = re.sub(r"[\(\[\{][^)\]\}]{0,100}[\)\]\}]", bersihin_group, nama)
    for kata in kata_varian:
        nama = re.sub(rf"\b{re.escape(kata)}\b", " ", nama, flags=re.IGNORECASE)

    nama = re.sub(r"\s+", " ", nama).strip(" -_()[]{}.")
    if not nama:
        return Path(str(rel_path)).stem.lower().strip()
    return nama

NP_CHAT_THRESHOLD = 9
async def update_dashboard (channel, embed):
    ch_id = channel.id
    msg_id = state.last_np_message.get(ch_id)
    jumlah = state.pesan_sejak_np.get(ch_id, 0)

    if msg_id and jumlah < NP_CHAT_THRESHOLD:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed)
            state.pesan_sejak_np[ch_id] = 0
            return msg
        except discord.HTTPException:
            state.last_np_message.pop(ch_id, None)
    
    msg = await channel.send(embed=embed)
    state.last_np_message[ch_id] = msg.id
    state.pesan_sejak_np[ch_id] = 0
    return msg

async def refresh_dashboard_np(guild_id):
    ch_id = state.np_channel.get(guild_id)
    if not ch_id:
        return
    bot = runtime.get_bot()
    if not bot:
        return
    channel = bot.get_channel(ch_id)
    if not channel:
        return
    from .commands.playback import create_embed_np
    embed = await create_embed_np(guild_id)
    if embed:
        await update_dashboard(channel, embed)

# bungkus ffmpeg + volume di satu tempat
def build_audio(source, volume=0.5):
    before_options = ""
    options = "-vn -loglevel panic"
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        before_options += " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    src = FFmpegPCMAudio(source=source, executable=config.ffmpeg_executable(), before_options=before_options, options=options)
    return PCMVolumeTransformer(src, volume=volume)

# ngurus timer keluar voice kalau bot nganggur
def cancel_idle_leave(guild_id):
    task = state.gabut.pop(guild_id, None)
    if task:
        print(f"[cancel_idle_leave] task ktemu, done ={task.done()}")
    if task and not task.done ():
        print(f"[cancel_idle_leave] batalin task untuk guild={guild_id}")
        task.cancel()

def schedule_leave(guild_id, voice_client, delay = 15 * 60):
    cancel_idle_leave(guild_id)        

    async def _job():
        try:
            await asyncio.sleep(delay)   
            if not voice_client or not voice_client.is_connected():
                return
            if voice_client.is_playing() or voice_client.is_paused():
                return
            save_queue(guild_id)
            state.queue_asli.pop(guild_id, None)
            state.play_queue.pop(guild_id, None)
            state.current_playing.pop(guild_id,  None)
            await voice_client.disconnect()
            print(f"Bot auto keluar voice karena idle {guild_id}")
        except asyncio.CancelledError:
            pass
        finally:
            if state.gabut.get(guild_id) is asyncio.current_task():
                state.gabut.pop(guild_id, None)

    state.gabut[guild_id] = asyncio.create_task(_job())

# buat repeat lagu yang sama tanpa lewat queue
async def replay_c(guild_id, voice_client):
    async with kunci_lagu(guild_id):
        lagu = state.current_playing.get(guild_id)
        if not lagu or not voice_client or not voice_client.is_connected():
            return
        vol = state.tingkat_suara.get(guild_id, 0.5)
        if isinstance (lagu, dict):
            fresh = await get_audio_source(lagu["webpage_url"])
            source = build_audio(fresh["url"], volume=vol)
        else:
            source = build_audio(str(config.music_root_dir() / lagu), volume=vol)

        voice_client.play(source, after=partial(after_play, guild_id, voice_client))
        state.started_at[guild_id] = time.time()
        state.paused_at.pop(guild_id, None)
        state.total_pause[guild_id] = 0

# callback abis lagu selesai / stream berhenti
def after_play(guild_id, voice_client, error):
    if error:
        print(f"[ERROR STREAM] guild {guild_id} error saat play: {error}")
        return
    try:
        if state.ulang_lagu.get(guild_id, False):
            loop = runtime.get_bot_loop()
            asyncio.run_coroutine_threadsafe(replay_c(guild_id, voice_client), loop)
            return
        if state.flag_shuffle.get(guild_id, False):
            shuffle_queue(guild_id)

        state.current_playing.pop(guild_id, None)
        loop = runtime.get_bot_loop()
        asyncio.run_coroutine_threadsafe(play_next(guild_id, voice_client), loop)

    except Exception as e:
        print (f"after_play handler error {e}")
        state.current_playing.pop(guild_id, None)            

# ambil item berikutnya dari queue terus coba puter
async def play_next(guild_id, voice_client):
    if not voice_client or not voice_client.is_connected():  
        state.current_playing.pop(guild_id, None)  
        return  

    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)

        # kalau queue habis tapi autoalir nyala, isi satu lagu dulu
        if not state.play_queue.get(guild_id) or len(state.play_queue[guild_id]) == 0:
            if state.mode_autoalir.get(guild_id, False):
                debug_autoalir(f"queue kosong dan autoalir nyala untuk guild={guild_id}")
                auto_item = pilih_lagu_auto(guild_id)

                if auto_item:
                    debug_autoalir(f"auto_item kepilih = {auto_item}")
                    print(f"[AUTOALIR] milih lagu otomatis: {auto_item}")
                    state.play_queue[guild_id].append(auto_item)
                else:
                    debug_autoalir("auto_item kosong")
                    print(f"[AUTOALIR] ga nemu lagu lanjutan buat guild {guild_id}")

            if not state.play_queue.get(guild_id) or len(state.play_queue[guild_id]) == 0:
                print(f"antrian kosong jir untuk guild {guild_id}")
                schedule_leave(guild_id, voice_client)
                return

        while state.play_queue[guild_id]:
            item = state.play_queue[guild_id].popleft()

            # bersihin juga dari queue tampilan biar dua-duanya sinkron
            try:
                if item in state.queue_asli.get(guild_id, []):
                    state.queue_asli[guild_id].remove(item)
            except ValueError:
                pass
            try:
                # kalau item youtube, refresh stream url terus play
                if isinstance(item, dict):
                    title = item["title"]
                    state.current_playing[guild_id] = item
                    vol = state.tingkat_suara.get(guild_id, 0.5)
                    fresh = await get_audio_source(item["webpage_url"])
                    source = build_audio(fresh["url"], volume=vol)
                    voice_client.play(source, after=partial(after_play, guild_id, voice_client))
                    state.started_at[guild_id] = time.time()
                    state.paused_at.pop(guild_id, None)
                    state.total_pause[guild_id] = 0
                    save_queue(guild_id)
                    asyncio.create_task(refresh_dashboard_np(guild_id))
                    print(f"Now playing YT: {title}")
                    return

                # kalau file lokal tinggal tembak ke ffmpeg
                file_rel_path = item
                path_full = config.music_root_dir() / file_rel_path
                if not path_full.exists():
                    print(f"file ilang, nooo:{path_full}")
                    continue

                state.current_playing[guild_id] = file_rel_path
                vol = state.tingkat_suara.get(guild_id, 0.5)
                source = build_audio(str(path_full), volume=vol)
                
                voice_client.play(source, after=partial(after_play, guild_id, voice_client))
                state.started_at[guild_id] = time.time()
                state.paused_at.pop(guild_id, None)
                state.total_pause[guild_id] = 0
                catat_selera(guild_id, file_rel_path)
                save_queue(guild_id)
                asyncio.create_task(refresh_dashboard_np(guild_id))
                return
            except Exception as e:
                print(f"Gagal ngeplay item berikutnya: {e}")
                state.current_playing.pop(guild_id, None)
                continue

    state.current_playing.pop(guild_id, None)
    print("gada lagu yang valid yang bisa di puter jir")