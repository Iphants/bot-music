from mutagen.flac import FLAC
from mutagen import File

def get_audio_metadata(file_path):
    audio = File(file_path)

    if not audio:
        return None
    tags = audio.tags or {}

    def ambil(tag_name):
        val = tags.get(tag_name)
        if not val:
            return "Unknown"
        if isinstance(val, list):
            return str(val[0])
        return str(val)
    return {
        "title": ambil("title"),
        "artist": ambil("artist"),
        "album": ambil("album"),
        "duration": int(audio.info.length) if audio.info and audio.info.length else 0
    }

def get_cover(audio):
    try:
        if isinstance(audio, FLAC):
            if audio.pictures:
                return audio.pictures[0].data
        if audio and audio.tags:
            for tag in audio.tags.values():
                if hasattr(tag, "data"):
                    return tag.data
    except Exception as e:
        print(f"error ambil cover: {e}")
    return None    
        