from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ALIAS_PATH = DATA_DIR / "sp_alias.json"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", str(t or "")).casefold().strip()
    return re.sub(r"\s+", " ", t)


def _load() -> dict:
    if not ALIAS_PATH.exists():
        return {}
    try:
        with ALIAS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ALIAS_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(ALIAS_PATH)


def get_alias(query: str) -> str | None:
    return _load().get(_norm(query))


def set_alias(query: str, judul_asli: str) -> None:
    data = _load()
    data[_norm(query)] = judul_asli
    _save(data)
