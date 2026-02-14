# bot-music-discord

Modular Discord music bot (local files) using `discord.py`.

## Run (any OS)

Set environment variables:

- `DISCORD_TOKEN`: your bot token
- `MUSIC_DIR`: folder containing your music files (mp3/wav/flac/m4a)
- `FFMPEG_PATH` (optional): path to ffmpeg binary (useful on Windows)

### Linux/macOS

```bash
export DISCORD_TOKEN="..."
export MUSIC_DIR="$HOME/Music"
python3 main.py
```

### Windows (PowerShell)

```powershell
$env:DISCORD_TOKEN="..."
$env:MUSIC_DIR="D:\Music"
# optional:
# $env:FFMPEG_PATH="C:\ffmpeg\bin\ffmpeg.exe"
python main.py
```

## Notes

- Default `MUSIC_DIR` (if not set): `~/Music` if it exists, otherwise `./Music`.
- FFmpeg default: `ffmpeg` (must be available in PATH, or set `FFMPEG_PATH`).

