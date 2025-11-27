# Discord Local Music Bot

Bot musik Discord yang memutar file audio langsung dari folder lokal pada PC/server. Dirancang untuk performa stabil, pencarian cepat menggunakan cache + fuzzy search, serta mendukung queue per guild.

---

##  Fitur Utama

- Putar musik dari folder lokal
- Fuzzy Search untuk menangani typo
- Sistem cache agar pencarian cepat
- Queue per guild
- Auto play lagu berikutnya
- Pause, resume, skip
- Volume control
- Menghapus duplikat hasil pencarian

---

##  Struktur 
```
MusicBot/
┣ musik/                 # folder musik lokal
┣ dasdas.py              # file utama bot
┣ README.md
```
---

##  Install & Setup

1. Install dependency:
2. ```
   pip install discord.py
   pip install PyNaCl
  
3. Pastikan FFmpeg sudah terinstall:
   ```
   ffmpeg -version
   ```
4. Masukkan token bot:
   bot.run("token_botmu")

5. Atur lokasi folder musik:
   daftar_musik = r"E:\Music"

---

##  Menjalankan Bot

dasdas.py

---

##  Command

| command           |                                   |
| ----------------  | ----------------------------      |
| !play <judul>     | -Putar lagu / masuk antrian      |
| !search <judul>   | -Cari file musik lokal           |
| !queue            | -Lihat antrian                   |
| !pause            | -Pause                           |
| !resume           | -Resume                          |
| !next             | -Skip lagu                       |
| !now              | -Lihat lagu yang sedang diputar  |
| !refresh          | -Refresh cache musik             |
| !join             | -Bot masuk voice                 |
| !leave            | -Bot keluar voice                |

##  Cara Kerja Singkat

1. User mengirim !play <judul>.
2. Bot mencari file melalui cache atau fuzzy search.
3. Lagu dimasukkan ke queue.
4. Jika idle, lagu dimainkan.
5. Setelah lagu selesai, callback after_play() → play_next().
6. Queue habis → bot berhenti.

---

##  Konsep yang Dipakai

- deque untuk antrian FIFO
- difflib.get_close_matches untuk fuzzy search
- Cache timestamp untuk menghindari scan folder berulang
- FFmpegPCMAudio untuk audio streaming
- Recursive callback untuk auto next
- set() untuk hilangkan duplikat hasil pencarian

---

##  Batasan

- Hanya memutar file dari storage lokal
- Bot harus berjalan di PC/server yang selalu aktif
- Tidak mendukung YouTube / Spotify

---

##  Lisensi

Open-source — bebas dikembangkan.
