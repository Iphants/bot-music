from __future__ import annotations
import json
from collections import deque
from pathlib import Path
from . import state

MAX_HISTORY_AUTOALIR = 7
MAX_HISTORY_MID = 18
MAX_HISTORY_JDUL = 6
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "autoalir_state.json"

# key json dibalikin lagi ke int guild id
def keys_int(d: dict) -> dict:
    hasil = {}
    for k, v in d.items():
        try:
            hasil[int(k)] = v
        except (TypeError, ValueError):
            continue
    return hasil

# dump state autoalir ke file json
def save_autoalir_state() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ini masih digebleg jadi satu map gede, nanti pecah kalau udah nyebelin
    data = {"selera_guild": {str(guild_id): lagu_map for guild_id, lagu_map in state.selera_guild.items()}, "lagu_terakhir_lokal": {str(guild_id): lagu for guild_id, lagu in state.lagu_terakhir_lokal.items()}, "history_autoalir": { str(guild_id): list(dq) for guild_id, dq in state.history_autoalir.items()}, "history_mid_autoalir": { str(guild_id): list(dq) for guild_id, dq in state.history_mid_autoalir.items()}, "history_jdul_autoalir": { str(guild_id): list(dq) for guild_id, dq in state.history_jdul_autoalir.items()}, }

    temp_file = STATE_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    temp_file.replace(STATE_FILE)

# load balik state autoalir dari file kalau ada
def load_autoalir_state() -> None:
    if not STATE_FILE.exists():
        return
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        print("[AUTOALIR STORE] gagal load JSON, file rusak / tidak valid")
        return
    
    selera_raw = keys_int(data.get("selera_guild", {}))
    terakhir_raw = keys_int(data.get("lagu_terakhir_lokal", {}))
    history_raw = keys_int(data.get("history_autoalir", {}))
    history_mid_raw = keys_int(data.get("history_mid_autoalir", {}))
    history_jdul_raw = keys_int(data.get("history_jdul_autoalir", {}))

    state.selera_guild = {guild_id: dict(lagu_map) if isinstance(lagu_map, dict) else {} for guild_id, lagu_map in selera_raw.items()}
    state.lagu_terakhir_lokal = {guild_id: lagu for guild_id, lagu in terakhir_raw.items() if isinstance(lagu, str)}
    state.history_autoalir = {guild_id: deque([item for item in items if isinstance(item, str)],maxlen=MAX_HISTORY_AUTOALIR,) for guild_id, items in history_raw.items() if isinstance(items, list)}
    state.history_mid_autoalir = {guild_id: deque([item for item in items if isinstance(item, str)],maxlen=MAX_HISTORY_MID,) for guild_id, items in history_mid_raw.items() if isinstance(items, list)}
    state.history_jdul_autoalir = {guild_id: deque([item for item in items if isinstance(item, str)],maxlen=MAX_HISTORY_JDUL,) for guild_id, items in history_jdul_raw.items() if isinstance(items, list)}

    print("[AUTOALIR STORE] state autoalir berhasil diload")

# queue persistence

QUEUE_FILE = DATA_DIR/"queue_state.json"

def _load_queue_data(file_path):
    if not file_path.exists():
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        print("[QUEUE STORE] gagal load JSON, file rusak/gak valid")
        return {}

def save_queue(guild_id) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_queue_data(QUEUE_FILE)

    data[str(guild_id)] = {
        "queue_asli": list(state.queue_asli.get(guild_id, [])),
        "play_queue": list(state.play_queue.get(guild_id, [])),
        "current_playing": state.current_playing.get(guild_id),
    }

    temp_file = QUEUE_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp_file.replace(QUEUE_FILE)

def load_queue() -> None:
    data = _load_queue_data(QUEUE_FILE)
    if not data:
        return
    
    parsed_data = keys_int(data)
    for guild_id, entri in parsed_data.items():
        if not isinstance(entri, dict):
            continue
        q_asli = entri.get("queue_asli", [])
        q_play = entri.get("play_queue", [])
        if not isinstance(q_asli, list):
            q_asli = []
        if not isinstance(q_play, list):
            q_play = []

        dq_asli = deque(q_asli)
        dq_play = deque(q_play)
        current = entri.get("current_playing")
        if current:
            dq_play.appendleft(current)
            dq_asli.appendleft(current)

        state.queue_asli[guild_id] = dq_asli
        state.play_queue[guild_id] = dq_play    
    print("[QUEUE STORE] state queue berhasil diload")