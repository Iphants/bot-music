import yt_dlp
import asyncio

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
