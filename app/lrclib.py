from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import requests

BASE = "https://lrclib.net/api"
HEADERS = {"User-Agent": "bot-music/1.0 (https://github.com/Iphants/bot-music)"}

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_PATH = DATA_DIR / "lrclib_cache.json"

TIMEOUT = 10
NEGATIVE_TTL_SECONDS = 7 * 24 * 60 * 60


def _now() -> int:
    return int(time.time())


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = unicodedata.normalize("NFKC", str(value))
    value = value.casefold()
    value = value.strip()

    value = re.sub(r"\s+", " ", value)
    return value


def _normalize_duration(durasi: int | float | str | None) -> int:
    if durasi is None:
        return 0

    try:
        dur = float(durasi)
    except (TypeError, ValueError):
        return 0

    if dur > 10_000:
        dur = dur / 1000

    return max(0, int(round(dur)))


def _cache_key(judul: str, artist: str | None, durasi: int | float | str | None) -> str:
    title_norm = _normalize_text(judul)
    artist_norm = _normalize_text(artist)
    duration_norm = _normalize_duration(durasi)

    return f"{artist_norm}|{title_norm}|{duration_norm}"


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}

    try:
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        print("[LRCLIB CACHE] JSON rusak/ga valid, mulai dari kosong")
        return {}


def _save_cache(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp = CACHE_PATH.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    temp.replace(CACHE_PATH)


def _cache_get(key: str) -> str | None:
    cache = _load_cache()
    entri = cache.get(key)

    if not isinstance(entri, dict):
        return None

    if isinstance(entri.get("lrc"), str) and entri["lrc"].strip():
        return entri["lrc"]

    if entri.get("lrc") is None and entri.get("status") == "not_found":
        fetched_at = int(entri.get("fetched_at") or 0)
        if _now() - fetched_at < NEGATIVE_TTL_SECONDS:
            return None

    return None


def _cache_has_fresh_negative(key: str) -> bool:
    cache = _load_cache()
    entri = cache.get(key)

    if not isinstance(entri, dict):
        return False

    if entri.get("lrc") is not None or entri.get("status") != "not_found":
        return False

    fetched_at = int(entri.get("fetched_at") or 0)
    return _now() - fetched_at < NEGATIVE_TTL_SECONDS


def _cache_set_hit(
    key: str,
    lrc: str,
    *,
    asal: str,
    judul: str,
    artist: str | None,
    durasi: int,
    match_data: dict[str, Any] | None = None,
) -> None:
    cache = _load_cache()
    cache[key] = {
        "status": "ok",
        "source": "lrclib",
        "match_via": asal,
        "title": judul,
        "artist": artist,
        "duration": durasi,
        "lrc": lrc,
        "fetched_at": _now(),
    }

    if match_data:
        cache[key]["match"] = {
            "trackName": match_data.get("trackName"),
            "artistName": match_data.get("artistName"),
            "albumName": match_data.get("albumName"),
            "duration": match_data.get("duration"),
            "id": match_data.get("id"),
            "instrumental": match_data.get("instrumental"),
        }

    _save_cache(cache)


def _cache_set_not_found(
    key: str,
    *,
    judul: str,
    artist: str | None,
    durasi: int,
    reason: str,
) -> None:
    cache = _load_cache()
    cache[key] = {
        "status": "not_found",
        "source": "lrclib",
        "title": judul,
        "artist": artist,
        "duration": durasi,
        "lrc": None,
        "reason": reason,
        "fetched_at": _now(),
    }
    _save_cache(cache)


def _ekstrak_lrc(data: dict[str, Any] | None) -> str | None:
    if not isinstance(data, dict):
        return None

    synced = data.get("syncedLyrics")
    if isinstance(synced, str) and synced.strip():
        return synced.strip()

    plain = data.get("plainLyrics")
    if isinstance(plain, str) and plain.strip():
        return plain.strip()

    return None


def get_exact(
    judul: str,
    artist: str | None,
    durasi: int | float | str | None,
    album: str | None = None,
) -> dict[str, Any] | None:
    durasi_detik = _normalize_duration(durasi)

    params: dict[str, Any] = {
        "track_name": judul,
        "artist_name": artist or "",
    }

    if durasi_detik:
        params["duration"] = durasi_detik

    if album:
        params["album_name"] = album

    r = requests.get(
        f"{BASE}/get",
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    if r.status_code == 404:
        return None

    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else None


def search(judul: str, artist: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"track_name": judul}

    if artist:
        params["artist_name"] = artist

    r = requests.get(
        f"{BASE}/search",
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list):
        return []

    return [x for x in data if isinstance(x, dict)]


def _pilih_search_terbaik(
    hasil: list[dict[str, Any]],
    durasi: int,
) -> dict[str, Any] | None:
    if not hasil:
        return None

    if durasi:
        hasil = sorted(
            hasil,
            key=lambda x: abs(int(x.get("duration") or 0) - durasi),
        )

    return hasil[0]


def _ambil_data_lirik(
    judul: str,
    artist: str | None,
    durasi: int,
    album: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    hit = get_exact(judul, artist, durasi, album)
    if hit:
        return hit, "exact"

    hasil = search(judul, artist)
    if not hasil:
        return None, "kosong"

    best = _pilih_search_terbaik(hasil, durasi)
    if not best:
        return None, "kosong"

    return best, "search"


def ambil_lirik(
    judul: str,
    artist: str | None,
    durasi: int | float | str | None,
    album: str | None = None,
) -> str | None:
    """
    Ambil lirik dari LRCLIB.

    Return:
      - string .lrc mentah kalau ketemu
      - plain lyrics string kalau synced lyrics tidak ada
      - None kalau tidak ketemu / instrumental / error request

    Catatan:
      Fungsi ini sengaja tidak raise request error ke caller bot,
      supaya command Discord tidak ikut crash cuma karena LRCLIB error.
    """
    if not judul:
        return None

    durasi_detik = _normalize_duration(durasi)
    key = _cache_key(judul, artist, durasi_detik)

    cached = _cache_get(key)
    if cached:
        return cached

    if _cache_has_fresh_negative(key):
        return None

    try:
        data, asal = _ambil_data_lirik(judul, artist, durasi_detik, album)
    except requests.RequestException as e:
        print(f"[LRCLIB] request gagal: {e}")
        return None

    if not data:
        _cache_set_not_found(
            key,
            judul=judul,
            artist=artist,
            durasi=durasi_detik,
            reason=asal,
        )
        return None

    lrc = _ekstrak_lrc(data)
    if not lrc:
        _cache_set_not_found(
            key,
            judul=judul,
            artist=artist,
            durasi=durasi_detik,
            reason="empty_or_instrumental",
        )
        return None

    _cache_set_hit(
        key,
        lrc,
        asal=asal,
        judul=judul,
        artist=artist,
        durasi=durasi_detik,
        match_data=data,
    )
    return lrc


def _ringkas_lrc(lrc: str | None) -> str:
    if not lrc:
        return "ga ketemu"

    baris = lrc.strip().splitlines()
    if not baris:
        return "kosong"

    is_synced = bool(re.match(r"^\[\d{1,2}:\d{2}", baris[0].strip()))
    tipe = "SYNCED" if is_synced else "PLAIN"

    return f"{tipe}, {len(baris)} baris\n  contoh: {baris[0]}"


if __name__ == "__main__":
    tes = [
        ("sakura biyori and time machine", "Ado", 206),
        ("Shoujo Rei", "More More Jump!", 291),
        ("lagu ngaco yang ga ada", "siapa tau", 180),
    ]

    for judul, artist, durasi in tes:
        print(f"\n=== {judul} - {artist} ({durasi}s) ===")
        lrc = ambil_lirik(judul, artist, durasi)
        print(" ", _ringkas_lrc(lrc))
