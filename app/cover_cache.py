from __future__ import annotations
import asyncio
import json
import os
import time
from pathlib import Path

import requests
from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.id3 import APIC

from . import config

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
COVER_URL = DATA_DIR / "cover_urls.json"

CATBOX_API = "https://catbox.moe/user/api.php"
UPLOAD_TIMEOUT = 15
JEDA_MIN = 1.0

_sem_upload = asyncio.Semaphore(1)
_inflight: dict[str, asyncio.Task] = {}
_last_up = 0.0

def _load_cache() -> dict:
    if not COVER_URL.exists():
        return {}
    try:
        with COVER_URL.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        print("[COVER CACHE] JSON rusak/ga valid, mulai dari kosong")
        return {}

def _save_cache(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True) 
    temp = COVER_URL.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(COVER_URL)

def _key_dari(file_rel: str) -> str:
    return str(file_rel).replace("\\", "/").strip("/").lower() 

def _mtime_save(full_path: Path):
    try:
        return os.path.getmtime(full_path)
    except OSError:
        return None

def _ekstra_cover(full_path: Path):
    try:
        audio = MutagenFile(full_path)
        if isinstance(audio, FLAC) and audio.pictures:
            return audio.pictures[0].data, "cover.jpg"
        if audio and audio.tags:
            covr = audio.tags.get("covr")
            if covr:
                first = covr[0] if isinstance(covr, (list, tuple)) else covr
                return bytes(first), "cover.jpg"
            for tag in audio.tags.values():
                if isinstance(tag, APIC):
                    return tag.data, "cover.jpg"
    except Exception as e:
        print(f"[COVER CACHE] gagal ekstrak cover: {e}")
    return None, None

def _up_catbox(cover_bytes: bytes, filename: str = "cover.jpg"):
    try:
        resp = requests.post(
            CATBOX_API,
            files={"fileToUpload": (filename, cover_bytes, "image/jpeg")},
            data={"reqtype": "fileupload"},
            timeout=UPLOAD_TIMEOUT,
        )
        if resp.status_code == 200 and resp.text.startswith("https://"):
            return resp.text.strip()
        print(f"[COVER CACHE] upload gagal: {resp.status_code} {resp.text[:120]}")
        return None
    except Exception as e:
        print(f"[COVER CACHE] upload exception: {e}")
        return None

async def _prosses_key(key: str, full_path: Path, mtime):
    global _last_up

    cover_bytes, filename = _ekstra_cover(full_path)
    if not cover_bytes:
        return None

    async with _sem_upload:
        sisa = JEDA_MIN - (time.time() - _last_up)
        if sisa > 0:
            await asyncio.sleep(sisa)

        loop = asyncio.get_running_loop()
        url = await loop.run_in_executor(None, _up_catbox, cover_bytes, filename)
        _last_up = time.time()

    if not url:
        return None

    data = _load_cache()
    data[key] = {"url": url, "mtime": mtime}
    _save_cache(data)
    return url

async def resolve_cover(file_rel):
    if not file_rel or not isinstance(file_rel, str):
        return None

    full_path = config.music_root_dir() / file_rel
    mtime = _mtime_save(full_path)
    if mtime is None:
        return None

    key = _key_dari(file_rel)
    cache = _load_cache()
    entri = cache.get(key)
    if isinstance(entri, dict) and entri.get("mtime") == mtime and entri.get("url"):
        return entri["url"]

    if key in _inflight:
        return await _inflight[key]

    task = asyncio.create_task(_prosses_key(key, full_path, mtime))
    _inflight[key] = task
    try:
        return await task
    finally:
        _inflight.pop(key, None)