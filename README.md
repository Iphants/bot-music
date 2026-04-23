# Discord Local Music Bot (Modular)

Modular Discord music bot untuk memutar file musik lokal menggunakan `discord.py`.
Bot ini mendukung queue per guild, fuzzy search, metadata audio, library navigator, autoalir lagu lokal, serta sistem cache untuk menjaga performa.

---

## Fitur Utama

- Memutar musik lokal (`mp3` / `wav` / `flac` / `m4a`)
- Fuzzy search (tetap ketemu meski typo)
- Cache folder musik (scan sekali, pakai berkali-kali)
- Queue per guild (server)
- Metadata lagu (title / artist / album / duration)
- Cover album pada embed
- Library browser langsung dari Discord
- Autoalir lagu lokal saat antrian habis
- Penyimpanan state autoalir
- YouTube playback
- Volume control
- Repeat / shuffle / remove queue

---

## Konsep & Arsitektur

| Konsep                      | Kegunaan                                      |
| --------------------------- | --------------------------------------------- |
| `deque`                     | Struktur antrian FIFO lagu                    |
| `difflib.get_close_matches` | Fuzzy search                                  |
| `FFmpegPCMAudio`            | Streaming audio ke voice channel              |
| `PCMVolumeTransformer`      | Kontrol volume playback                       |
| Callback chaining           | Auto play lagu berikutnya                     |
| Cache timestamp             | Hindari scan folder berulang                  |
| Metadata cache              | Hindari baca tag audio berulang               |
| Autoalir state store        | Menyimpan history / selera autoalir ke file   |

---

## Alur Kerja Bot

1. User menjalankan command `!play <judul>` atau memilih lagu dari library
2. Bot mencari lagu via cache + fuzzy search / relative path
3. Metadata dan cover dibaca lalu disimpan ke cache
4. Lagu dimasukkan ke queue guild
5. Jika belum ada lagu diputar, bot langsung memutar lagu
6. Setelah lagu selesai, bot otomatis memutar lagu berikutnya
7. Jika antrian habis dan `autoalir` aktif, bot mencari lagu lokal yang masih relevan
8. Jika bot idle selama 15 menit, bot keluar dari voice channel

---

## Command Bot

| Command                  | Fungsi                                      |
| ------------------------ | ------------------------------------------- |
| `!join`                  | Bot masuk ke voice channel user             |
| `!leave`                 | Bot keluar dari voice channel               |
| `!play <judul>`          | Putar / tambahkan lagu lokal ke queue       |
| `!search <judul>`        | Cari lagu lokal                             |
| `!pick <nomor>`          | Putar hasil pencarian                       |
| `!library`               | Buka library musik                          |
| `!library <halaman>`     | Buka library pada halaman tertentu          |
| `!open <nomor>`          | Buka folder / putar item yang terlihat      |
| `!back`                  | Kembali ke folder sebelumnya                |
| `!queue`                 | Lihat daftar antrian                        |
| `!pause` / `!resume`     | Pause / lanjutkan musik                     |
| `!next`                  | Skip lagu                                   |
| `!repeat`                | Nyalakan / matikan repeat                   |
| `!shuffle`               | Acak urutan queue                           |
| `!remove <angka/nama>`   | Hapus lagu dari antrian                     |
| `!now`                   | Lihat lagu yang sedang diputar              |
| `!volume <0-100>`        | Atur volume bot                             |
| `!refresh`               | Refresh cache musik                         |
| `!yt <judul>`            | Cari dan putar lagu dari YouTube            |
| `!autoalir on/off`       | Nyalakan / matikan autoalir                 |
| `!help`                  | Menampilkan bantuan                         |
| `!help <command>`        | Menampilkan detail command tertentu         |

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

```bash
export DISCORD_TOKEN="YOUR_TOKEN"
export MUSIC_DIR="$HOME/Music"
python3 main.py
```
---

### Windows (PowerShell)

```bash
$env:DISCORD_TOKEN="YOUR_TOKEN"
$env:MUSIC_DIR="D:\Music"
python main.py
```
```optional (kalau ffmpeg tidak ada di path)
$env:FFMPEG_PATH="C:\ffmpeg\bin\ffmpeg.exe"
