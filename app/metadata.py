from mutagen.id3 import APIC
from mutagen.flac import FLAC
from mutagen import File


# rapihin isi tag jadi string biasa dulu
def _tag_val(value):
    if not value:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    if hasattr(value, "text"):
        value = value.text[0] if value.text else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# nyoba beberapa nama tag sampe dapet isi
def _tag_ambil(tags, *nama_tags):
    if not tags:
        return None

    for nama in nama_tags:
        value = _tag_val(tags.get(nama))
        if value:
            return value

    nama_lower = {nama.lower() for nama in nama_tags}
    for key, value in tags.items():
        if str(key).lower() in nama_lower:
            value = _tag_val(value)
            if value:
                return value
    return None

# metadata dasar lagu diambil di sini
def get_audio_metadata(file_path):
    audio = File(file_path)

    if not audio:
        return None
    try:
        easy_audio = File(file_path, easy=True)
        easy_tags = easy_audio.tags if easy_audio and easy_audio.tags else {}
    except TypeError:
        easy_tags = {}

    raw_tags = audio.tags or {}

    # helper kecil doang, cuma kepake buat fungsi ini
    def ambil(easy_names, raw_names):
        return (
            _tag_ambil(easy_tags, *easy_names)
            or _tag_ambil(raw_tags, *raw_names)
            or "Unknown"
        )
    
    return {
        "title": ambil(("title",), ("title", "TIT2", "\xa9nam")),
        "artist": ambil(
            ("artist", "albumartist"),
            ("artist", "ARTIST", "TPE1", "\xa9ART", "aART"),
        ),
        "album": ambil(("album",), ("album", "ALBUM", "TALB", "\xa9alb")),
        "duration": int(audio.info.length) if audio.info and audio.info.length else 0
    }

# nyari cover art kalau file punya
def get_cover(file_path):
    try:
        audio = File(file_path)
        if isinstance(audio, FLAC):
            if audio.pictures:
                return audio.pictures[0].data
        if audio and audio.tags:
            cover = audio.tags.get("covr")
            if cover:
                first_cover = cover[0] if isinstance(cover, (list, tuple)) else cover
                return bytes(first_cover)
            
            for tag in audio.tags.values():
                if isinstance(tag, APIC):
                    return tag.data
                if isinstance(tag, (list, tuple)):
                    for item in tag:
                        if isinstance(item, (bytes, bytearray)):
                            return bytes(item)
                        if hasattr(item, "data"):
                            return item.data
                if hasattr(tag, "data"):
                    return tag.data
    except Exception as e:
        print(f"error ambil cover: {e}")
    return None
