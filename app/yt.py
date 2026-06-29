import yt_dlp
import asyncio

# setting yt-dlp numpuk di sini
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
        "node": {
            "path": "/usr/bin/node"
        },
    },
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# ambil info audio dari yt di sini, dipakai command !yt dan replay/auto-next YT
async def get_audio_source(query: str):
    loop = asyncio.get_event_loop()

    # kerja beratnya dilempar ke thread biar loop bot ga kesedak
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
