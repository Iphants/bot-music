from __future__ import annotations
import os
from pathlib import Path
import discord
import json

# input token/path interaktif dipakai setup_inter waktu env belum siap
def input_sensor(prompt: str) -> str:
    # branch windows, biar input token ga aneh
    if os.name == "nt":
        import msvcrt

        chars = []
        print(prompt, end="", flush=True)

        while True:
            ch = msvcrt.getwch()

            if ch in ("\r", "\n"):
                print()
                break
            if ch == "\003":
                raise KeyboardInterrupt
            if ch in ("\b", "\x7f"):
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue
            chars.append(ch)
        return "".join(chars)
    
    # selain windows jatohnya pake mode terminal biasa
    import sys
    import termios
    import tty

    if not sys.stdin.isatty():
        return input(prompt)
    
    chars = []
    print(prompt, end="", flush=True)

    fd = sys.stdin.fileno()
    old_sett = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)

            if ch in ("\r", '\n'):
                print()
                break
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\x7f", "\b"):
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue
            chars.append(ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_sett)
    return "".join(chars)

# fallback MUSIC_DIR kalau env/config lokal belum ngasih path
def default_music_di() -> Path:
    return (Path.cwd() / "Music").resolve()

# dipakai setup_inter buat validasi folder musik sebelum bot jalan
def ada_isi(path: Path) -> bool:
    ext_ok = (".mp3", ".wav", ".flac", ".m4a")

    if not path.exists() or not path.is_dir():
        return False
    try:
        for item in path.rglob("*"):
            if item.is_file() and item.suffix.lower() in ext_ok:
                return True
    except OSError:
        return False
    return False

# setup awal env lokal, dipanggil main.py tiap start
def setup_inter() -> None:
    local_config = load_local()
    apply_config(local_config)

    berubah = False
    token = os.environ.get("DISCORD_TOKEN")

    if not token:
        token = input_sensor("Masukkin token DC: ").strip()
        if not token:
            raise RuntimeError("token DC kosong, bot batal jalan.")
        os.environ["DISCORD_TOKEN"] = token
        local_config["DISCORD_TOKEN"] = token
        berubah = True

    env_music = os.environ.get("MUSIC_DIR")
    def_dir = default_music_di()
    tnya_path = False

    if not env_music:
        tnya_path = True
    else:
        path_env = Path(env_music).expanduser().resolve()
        if not ada_isi(path_env):
            print(f"MUSIC_DIR skrng ga valid / kosong: {path_env}")
            tnya_path = True    

    if tnya_path:
        print(f"Defauld folder musik: {def_dir}")
        jwab = input("Masukkin path folder musik, atau enter untuk pake default ./Music: ").strip()

        if jwab:
            music_path = Path(jwab).expanduser().resolve()
        else:
            music_path = def_dir

        music_path.mkdir(parents=True, exist_ok=True)
        os.environ["MUSIC_DIR"] = str(music_path)
        local_config["MUSIC_DIR"] = str(music_path)
        berubah = True

        if not ada_isi(music_path):
            print(f"warn: folder kosong / blom ada file audio: {music_path}")
    if berubah:
        save_local(local_config)
        print(f"[CONFIG] config local disimpan ke {LOCAL_CNFG}")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOCAL_CNFG = DATA_DIR / "local_cnfg.json"

# baca config lokal yang dibuat setup_inter / guard fallback
def load_local() -> dict:
    if not LOCAL_CNFG.exists():
        return{}
    try:
        with LOCAL_CNFG.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        print("[CONFIG] local_config.json rusak / gagal di baca, bakal di setup ulang")
        return {}
    
# tulis config lokal secara atomic biar file ga gampang corrupt
def save_local (data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = LOCAL_CNFG.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp_file.replace(LOCAL_CNFG)

# masukin config lokal ke env kalau env asli belum diset
def apply_config (data: dict) -> None:
    token = data.get("DISCORD_TOKEN")
    music_dir = data.get("MUSIC_DIR")
    ffmpeg_path = data.get("FFMPEG_PATH")

    if token and not os.environ.get("DISCORD_TOKEN"):
        os.environ["DISCORD_TOKEN"] = str(token)
    if music_dir and not os.environ.get("MUSIC_DIR"):
        os.environ["MUSIC_DIR"]  = str(music_dir)
    if ffmpeg_path and not os.environ.get("FFMPEG_PATH"):
        os.environ["FFMPEG_PATH"] = str(ffmpeg_path)   

# intent bot yang emang dipake sekarang
def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.guilds = True
    intents.members = True
    return intents

# root folder musik aktif
def music_root_dir() -> Path:
    env = os.environ.get("MUSIC_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return default_music_di()

# ffmpeg ambil dari env, kalau ga ada ya ngandelin PATH
def ffmpeg_executable() -> str:
    """
    FFmpeg binary name/path.
    - FFMPEG_PATH env var can point to a full path (recommended on Windows)
    - Otherwise rely on PATH lookup ("ffmpeg")
    """
    return os.environ.get("FFMPEG_PATH", "ffmpeg")

# token bot wajib ada sebelum jalan
def discord_token() -> str:
    """
    Discord bot token from environment.
    """
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        # sengaja dibiarin meledak di awal biar ketahuan dari start
        raise RuntimeError(
            "Missing DISCORD_TOKEN env var. "
            "Set it before running: DISCORD_TOKEN=... python main.py"
        )
    return token

# cache file musik dianggap basi setelah segini detik
CACHE_DURATION_SECONDS: int = 30
