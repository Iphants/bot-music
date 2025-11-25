# bot-music
-
# Discord Local Music Bot

## Deskripsi

Bot ini adalah Discord Music Bot yang memutar file musik lokal dari folder di PC/server. Mendukung antrian per guild, fuzzy search, auto-play next, dan sistem cache supaya pencarian lebih cepat.

---

## Fitur Utama

* Fuzzy Search (pencarian mirip meskipun typo)
* Cache folder musik
* Queue per guild
* Auto next track
* Duplicate filtering
* Volume control

---

## Alur Kerja Bot

1. User menjalankan command **!play <judul>**
2. Bot melakukan pencarian lagu melalui sistem cache + fuzzy search
3. Lagu dimasukkan ke queue guild terkait
4. Jika tidak ada lagu sedang dimainkan → bot langsung mainkan lagu pertama
5. Setelah lagu selesai → `after_play()` memanggil `play_next()`
6. Lagu berikutnya dimainkan otomatis jika queue masih ada isinya

---

##  Konsep

| Konsep                      | Kegunaan                               |
| --------------------------- | -------------------------------------- |
| `deque`                     | Struktur antrian FIFO untuk queue lagu |
| `difflib.get_close_matches` | Fuzzy Search                           |
| `set()`                     | Menghapus duplikat hasil pencarian     |
| `FFmpegPCMAudio`            | Streaming audio                        |
| Recursive callback          | Auto play next                         |
| Cache timestamp             | Mencegah scan folder berulang          |

---

## Command Bot

| Command              | Fungsi                              |
| -------------------- | ----------------------------------- |
| `!play <judul>`      | Putar lagu / queue jika sedang play |
| `!search <judul>`    | Cari judul musik lokal              |
| `!queue`             | Lihat daftar antrian                |
| `!pause` / `!resume` | Pause / resume musik                |
| `!next`              | Skip lagu                           |
| `!now`               | Lihat lagu yang sedang diputar      |
| `!refresh`           | Refresh cache musik                 |
| `!leave`             | Bot keluar dari voice               |

---

## Struktur Proyek

```
MusicBot
┣ musik/               # folder musik lokal
┣ bot.py               # file utama bot
┣ README.md            # dokumentasi
```

---

## Lisensi

Open-source — bebas dikembangkan.

---

Silakan gunakan dan modifikasi. Bila ingin ditambahkan contoh kode OOP / diagram arsitektur, tinggal bilang
