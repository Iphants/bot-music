# Discord Local Music Bot (Modular)

Modular Discord music bot untuk memutar file musik lokal menggunakan `discord.py`.
Mendukung queue per guild, fuzzy search, auto-play, dan sistem cache untuk performa.

---

## Fitur Utama

- Memutar musik lokal (mp3 / wav / flac / m4a)
- Fuzzy search (tetap ketemu meski typo)
- Cache folder musik (scan sekali, pakai berkali-kali)
- Queue per guild (server)
- Auto play lagu berikutnya
- Duplicate filtering
- Volume control (still develop)

---

## Konsep & Arsitektur

| Konsep                      | Kegunaan                               |
| --------------------------- | -------------------------------------- |
| `deque`                     | Struktur antrian FIFO lagu             |
| `difflib.get_close_matches` | Fuzzy search                            |
| `set()`                     | Filter duplikasi hasil pencarian        |
| `FFmpegPCMAudio`            | Streaming audio ke voice channel       |
| Callback chaining           | Auto play lagu berikutnya              |
| Cache timestamp             | Hindari scan folder berulang            |

---

## Alur Kerja Bot

1. User menjalankan command `!play <judul>`
2. Bot mencari lagu via cache + fuzzy search
3. Lagu dimasukkan ke queue guild
4. Jika belum ada lagu diputar =>  langsung play
5. Setelah lagu selesai =>  bot otomatis play lagu berikutnya
6. Queue habis =>  bot idle
7. Bot idle selama 15 menit => bot keluar dari channel

---

## Command Bot

| Command              | Fungsi                              |
| -------------------- | ----------------------------------- |
| `!play <judul>`      | Putar / tambahkan lagu ke queue     |
| `!search <judul>`    | Cari lagu lokal                     |
| `!queue`             | Lihat daftar antrian                |
| `!pause` / `!resume` | Pause / lanjutkan musik             |
| `!next`              | Skip lagu                           |
| `!now`               | Lagu yang sedang diputar            |
| `!refresh`           | Refresh cache musik                 |
| `!leave`             | Bot keluar dari voice channel       |
| `!yt`                | Mencari lagu dari youtube           |                

---

## Cara Menjalankan Bot

### Environment Variables

Wajib:
- `DISCORD_TOKEN` : token bot Discord
- `MUSIC_DIR`     : folder berisi file musik

Opsional:
- `FFMPEG_PATH`   : path ffmpeg (jika tidak ada di PATH)

---

### Linux / macOS

```
export DISCORD_TOKEN="YOUR_TOKEN"
```
```
export MUSIC_DIR="$HOME/Music"
```
```
python3 main.py
```

---

### Windows (PowerShell)
```
$env:DISCORD_TOKEN="YOUR_TOKEN"
```
```
$env:MUSIC_DIR="D:\Music"
```

optional:
```
$env:FFMPEG_PATH="C:\ffmpeg\bin\ffmpeg.exe"
```
```
python main.py
```

---

## Catatan

- Default `MUSIC_DIR`:
  - `~/Music` jika ada
  - fallback ke `./Music`
- Default ffmpeg: `ffmpeg` (harus tersedia di PATH)
---