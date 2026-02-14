from __future__ import annotations
import os
from pathlib import Path
import discord

def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.guilds = True
    intents.members = True
    return intents
def music_root_dir() -> Path:
    """
    Cross-platform music directory.

    Priority:
    - MUSIC_DIR env var (absolute or relative)
    - ~/Music if it exists
    - ./Music (relative to project)
    """
    env = os.environ.get("MUSIC_DIR")
    if env:
        return Path(env).expanduser().resolve()
    home_music = Path.home() / "Music"
    if home_music.exists():
        return home_music.resolve()
    return (Path.cwd() / "Music").resolve()
def ffmpeg_executable() -> str:
    """
    FFmpeg binary name/path.
    - FFMPEG_PATH env var can point to a full path (recommended on Windows)
    - Otherwise rely on PATH lookup ("ffmpeg")
    """
    return os.environ.get("FFMPEG_PATH", "ffmpeg")
def discord_token() -> str:
    """
    Discord bot token from environment.
    """
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing DISCORD_TOKEN env var. "
            "Set it before running: DISCORD_TOKEN=... python main.py"
        )
    return token
CACHE_DURATION_SECONDS: int = 30

