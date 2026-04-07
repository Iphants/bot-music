import yt_dlp
import asyncio

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "js_runtimes": {
        "node": {
            "path": "/usr/bin/node"
        },
    },
}
async def get_audio_source(query: str):
    def extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)

            if "entries" in info:
                info = info["entries"][0]

            return {
                "url": info["url"],
                "title": info["title"],
                "thumbnail": info.get("thumbnail")
            }

    return await asyncio.to_thread(extract)