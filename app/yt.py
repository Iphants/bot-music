import yt_dlp
import asyncio
import re
import unicodedata
from . import yt_override

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "nocheckcertificate": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "noplaylist": True,
    "ignoreerrors": True,
    "skip_download": True,
    "js_runtimes": {
        "node": {"path": "/usr/bin/node"},
    },
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


async def get_audio_source(query: str):
    loop = asyncio.get_event_loop()

    def extract():
        try:
            info = ytdl.extract_info(query, download=False)
            if "entries" in info:
                entries = info.get("entries")
                if not entries:
                    raise Exception("ga nemu hasil dair Youtube")
                info = entries[0]
            url = info.get("url")
            if not url:
                raise Exception("Ga dapet stream URL")
            return {
                "url": url,
                "title": info.get("title", "Unknown Title"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "webpage_url": info.get("webpage_url"),
                "uploader": info.get("uploader"),
            }
        except Exception as e:
            raise Exception(f"yt-dlp error: {e}")

    return await loop.run_in_executor(None, extract)


def _ekstrak_flat(query: str):
    opts = dict(YTDL_OPTIONS)
    opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(opts) as flat:
        info = flat.extract_info(query, download=False)
    return info.get("entries") or []


async def cari_yt(judul_query: str, target_durasi=None, n=5):
    loop = asyncio.get_event_loop()
    entries = await loop.run_in_executor(
        None, _ekstrak_flat, f"ytsearch{n}:{judul_query}"
    )
    if not entries:
        return None

    if target_durasi:

        def jarak(e):
            d = e.get("duration")
            if not d:
                return 10**9
            return abs(int(d) - int(target_durasi))

        entries = sorted(entries, key=jarak)

    for e in entries:
        vid = e.get("id") or e.get("url")
        if not vid:
            continue
        url = (
            vid
            if str(vid).startswith("http")
            else f"https://www.youtube.com/watch?v={vid}"
        )
        try:
            return await get_audio_source(url)
        except Exception as ex:
            print(f"[YT MATCH] gagal resolve {url}: {ex}")
            continue
    return None


def _kandidat_flat(query: str, n: int):
    opts = dict(YTDL_OPTIONS)
    opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(opts) as flat:
        info = flat.extract_info(f"ytsearch{n}: {query}", download=False)
    return info.get("entries") or []


async def debugsp_kandidat(judul: str, artist: str, durasi=False):
    queries = [
        f'"{judul}" "{artist}" official audio',
        f'"{judul}""{artist}" audio',
        f'"{judul} {artist} topic", f"{judul} {artist}",',
    ]
    loop = asyncio.get_event_loop()
    seen = set()
    kandidat = []
    for q in queries:
        entries = await loop.run_in_executor(None, _kandidat_flat, q, 8)
        for e in entries:
            vid = e.get("id")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            kandidat.append(e)

    print(f"\n[YT KANDIDAT] target: {judul} | {artist} | dur={durasi}")
    print(f"[YT KANDIDAT] total unik: {len(kandidat)}")
    for e in kandidat[:15]:
        print(
            f" id={e.get('id')} | dur={e.get('duration')} | "
            f"uploader={e.get('uploader')!r} | channel={e.get('channel')!r} | "
            f"title={e.get('title')!r}"
        )
    return kandidat


def _norm(teks: str) -> str:
    if not teks:
        return ""
    teks = unicodedata.normalize("NFKC", str(teks).casefold().strip())
    teks = re.sub(r"\s+", " ", teks)
    return teks


_BAD = {
    "cover": -90,
    "karaoke": -90,
    "カラオケ": -90,
    "instrumental": -80,
    "オフボーカル": -80,
    "off vocal": -80,
    "nightcore": -80,
    "slowed": -80,
    "sped up": -80,
    "1 hour": -80,
    "loop": -80,
    "remix": -60,
    "live": -35,
    "lyric video": -20,
    "歌ってみた": -60,
}
_BAD_CHANNEL = {
    "karaoke": -90,
    "joysound": -90,
    "歌っちゃ王": -90,
    "うたスキ": -90,
    "tj media": -80,
}


def _artist_utama(artist: str) -> str:
    if not artist:
        return ""
    return _norm(artist.split(",")[0])


def _skor_kandidat(e, judul, artist, durasi):
    jn = _norm(judul)
    an = _norm(artist)
    an1 = _artist_utama(artist)
    tn = _norm(e.get("title"))
    un = _norm(e.get("uploader") or e.get("channel"))
    dur = e.get("duration")

    skor = 0
    reason = []

    if jn and jn in tn:
        skor += 35
        reason.append("title match +50")
    else:
        kata = [k for k in jn.split() if len(k) > 1]
        if kata and sum(1 for k in kata if k in tn) >= max(1, len(kata) * 0.6):
            skor += 15
            reason.append("title partial +15")

    if an1 and an1 == un:
        skor += 65
        reason.append("channel==artist +65")
    elif an1 and an1 in un:
        skor += 45
        reason.append("artist in channel +45")
    elif an and an in tn:
        skor += 15
        reason.append("artist in title +15")
    if "- topic" in un:
        if an1 and (
            an1 in un.replace("- topic", "").strip()
            or un.replace("- topic", "").strip() in an1
        ):
            skor += 60
            reason.append("topic_artist +60")
        else:
            skor += 12
            reason.append("topic_generic+12")
    elif "vevo" in un:
        skor += 45
        reason.append("vevo +45")
    elif an1 and an1 in un and "official" in un:
        skor += 35
        reason.append("artist official +35")
    if "official audio" in tn:
        skor += 20
        reason.append("official_audio +20")
    elif "official video" in tn:
        skor += 12
        reason.append("official +12")
    elif "audio" in tn:
        skor += 10
        reason.append("audio +10")

    if durasi and dur:
        beda = abs(int(dur) - int(durasi))
        if beda <= 5:
            skor += 30
            reason.append(f"dur{beda}s+30")
        elif beda <= 15:
            skor += 20
            reason.append(f"dur{beda}s+20")
        elif beda <= 30:
            skor += 8
            reason.append(f"dur{beda}s+8")
        elif beda <= 60:
            skor -= 30
            reason.append(f"dur{beda}s-30")
        else:
            skor -= 80
            reason.append(f"dur{beda}s-80")

    for kata, penalti in _BAD.items():
        if kata in tn and kata not in jn:
            skor += penalti
            reason.append(f"{kata}{penalti}")

    for kata, penalti in _BAD_CHANNEL.items():
        if kata in un:
            skor += penalti
            reason.append(f"ch:{kata}{penalti}")

    return skor, reason


async def cari_yt_sp(judul: str, artist: str, durasi=None):
    paksa = yt_override.get_override(judul, artist)
    if paksa:
        print(f"[YT OVERRIDE] pakai manual: {paksa}")
        try:
            return await get_audio_source(paksa)
        except Exception as ex:
            print(f"[YT OVERRIDE] gagal resolve override, lanjut scoring: {ex}")
    queries = [
        f'"{judul}" "{artist}" official audio',
        f'"{judul}" "{artist}" audio',
        f"{judul} {artist} topic",
        f"{judul} {artist}",
    ]
    loop = asyncio.get_event_loop()
    best_posisi = {}
    seen = {}
    kandidat = {}
    for q in queries:
        entries = await loop.run_in_executor(None, _kandidat_flat, q, 8)
        for idx, e in enumerate(entries):
            vid = e.get("id")
            if not vid:
                continue
            kandidat.setdefault(vid, e)
            seen[vid] = seen.get(vid, 0) + 1
            if vid not in best_posisi or idx < best_posisi[vid]:
                best_posisi[vid] = idx
    if not kandidat:
        return None

    skored = []
    for vid, e in kandidat.items():
        s, reason = _skor_kandidat(e, judul, artist, durasi)
        pos = best_posisi.get(vid, 99)

        if pos == 0:
            s += 25
            reason.append("yt_rank#1+25")
        elif pos <= 2:
            s += 15
            reason.append(f"yt_rank#{pos + 1}+15")
        elif pos <= 4:
            s += 8
            reason.append(f"yt_rank#{pos + 1}+8")
        if seen.get(vid, 0) >= 3:
            s += 15
            reason.append("muncul_3query+15")
        elif seen.get(vid, 0) == 2:
            s += 8
            reason.append("muncul_2queery+8")
        skored.append((s, e, reason))
    skored.sort(key=lambda x: x[0], reverse=True)

    print(f"\n[YT RANK] target: {judul} | {artist} | dur={durasi}")
    for i, (s, e, reason) in enumerate(skored[:5], 1):
        print(
            f" {i}. score={s} | dur={e.get('duration')} | "
            f"up={e.get('uploader')!r} | title={e.get('title')!r}"
        )
        print(f"   {'+'.join(reason)}")

    for s, e, _ in skored:
        vid = e.get("id")
        url = f"https://www.youtube.com/watch?v={vid}"
        try:
            return await get_audio_source(url)
        except Exception as ex:
            print(f"[[YT RANK] gagal esolve {vid}: {ex}]")
            continue
    return None
