from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OVERRIDE_PATH = DATA_DIR / "yt_override.json"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", str(t or "")).casefold().strip()
    return re.sub(r"\s+", " ", t)


def _key(judul: str, artist: str) -> str:
    return f"{_norm(artist)}|{_norm(judul)}"


def _load() -> dict:
    if not OVERRIDE_PATH.exists():
        return {}
    try:
        with OVERRIDE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OVERRIDE_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(OVERRIDE_PATH)


def get_override(judul: str, artist: str) -> str | None:
    return _load().get(_key(judul, artist))


def set_override(judul: str, artist: str, url: str) -> None:
    data = _load()
    data[_key(judul, artist)] = url
    _save(data)
