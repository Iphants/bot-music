# Discord Local Music Bot

Bot Discord buat muter musik lokal pakai `discord.py`.
Fokus utamanya memang file lokal, tapi ada juga playback YouTube, library browser, autoalir, metadata lagu, cover album, dan cache biar bot nggak ngos-ngosan tiap command.

## Yang bisa dipakai sekarang

- Putar file lokal: `mp3`, `wav`, `flac`, `m4a`
- Cari lagu pakai fuzzy search
- Queue per guild
- Library browser langsung dari Discord
- Metadata lagu: title, artist, album, duration
- Cover album di embed
- YouTube playback lewat `!yt`
- Autoalir lagu lokal saat queue habis
- Simpan state autoalir ke file lokal
- Volume, repeat, shuffle, remove, clear queue
- Auto leave kalau voice kosong / idle

## Cara kerja singkat

Alurnya begini:

1. User jalanin `!play`, `!search`, `!library`, atau `!yt`
2. Bot ambil data lagu dari cache folder musik
3. Kalau lagu lokal, metadata dan cover dibaca lalu disimpan ke cache
4. Lagu masuk queue guild
5. Kalau belum ada yang muter, bot langsung play
6. Setelah lagu selesai, callback lanjut ke lagu berikutnya
7. Kalau queue habis dan `autoalir` nyala, bot nyari lagu lokal yang masih nyambung
8. Kalau bot idle terlalu lama, bot keluar dari voice

## Autoalir

Autoalir sekarang nyimpen beberapa hal:

- lagu terakhir per guild
- history file yang baru diputar
- history menengah buat lihat dominasi parent / artist
- history judul dasar
- selera guild dari lagu yang sering kepilih

State ini disimpan ke:

- `app/data/autoalir_state.json`

File itu cuma buat state lokal, jadi memang tidak ikut ke-push ke Git.

## system

Sekarang bot sudah punya beberapa guard biar nggak gampang salah jalan:

### 1. config saat startup

Waktu `main.py` jalan, bot manggil `config.setup_inter()`.
Bagian ini ngecek:

- `DISCORD_TOKEN` ada atau belum
- `MUSIC_DIR` ada atau belum
- folder musik valid atau tidak
- folder musik punya file audio atau tidak

Kalau token belum ada, bot bakal minta input.
Kalau path musik belum ada atau rusak, bot bakal minta path baru.

Jadi startup-nya nggak langsung mentok cuma karena env var belum disetel dari awal.

### 2. relative path file lokal

Command `!play` punya jalur khusus kalau user ngasih relative path langsung.
Sebelum file dipakai, bot cek:

- path kosong atau tidak
- path absolut atau tidak
- ada `..` atau tidak
- hasil resolve masih tetap di bawah root folder musik atau tidak
- file-nya beneran ada atau tidak

Ini nahan path aneh atau file di luar root musik ikut kebaca.

### 3. voice state

Beberapa command playback ngecek dulu:

- bot sudah ada di voice atau belum
- voice client masih connect atau tidak
- ada lagu yang lagi play/pause atau tidak

Contohnya kelihatan di `!play`, `!yt`, `!pause`, `!resume`, `!next`, `!leave`.

Jadi command nggak asal jalan waktu kondisi voice-nya belum siap.

### 4. idle / auto leave

Kalau voice channel kosong dari user non-bot, bot bikin task idle leave.
Kalau ada orang masuk lagi, task itu dibatalin.

Selain itu, kalau queue habis dan nggak ada lanjutan, bot juga masuk mode nunggu idle lalu keluar sendiri.

Default delay sekarang:

- `15 menit`

### 5. metadata dan cover

Sebelum embed lagu lokal dikirim, bot cek dulu:

- file audio masih ada atau tidak
- metadata kebaca atau tidak
- cover ada atau tidak

Kalau cover nggak ada, embed tetap dikirim.
Kalau metadata gagal dibaca, command lokal dihentikan dan user dikasih pesan error.

### 6. autoalir state

State autoalir disimpan ke JSON lokal lalu diload lagi waktu bot ready.
Pas load, bot ngecek:

- file state ada atau tidak
- JSON valid atau rusak
- key guild bisa diubah ke integer atau tidak
- item history memang string atau bukan

Kalau file rusak, bot nggak langsung crash. State itu cuma dilewati dan bot lanjut jalan.

### 7. command error

Di event `on_command_error`, bot nangkep error umum seperti:

- command tidak ada
- argumen kurang
- cooldown
- permission kurang
- invoke error

Tujuannya biar error nggak muncrat mentah ke user.

## Guard launcher

Guard ini dipakai kalau mau jalanin bot lewat jalur yang lebih aman, bukan langsung `python main.py`.

Yang dilakukan guard:

- bikin snapshoot kondisi project
- ngecek apakah file project berubah dari snapshoot terakhir
- menyimpan token Discord dalam bentuk terenkripsi
- membaca `MUSIC_DIR` dari config lokal
- menjalankan `main.py` dengan env var yang sudah disiapkan

Command guard:

| Command | Fungsi |
| --- | --- |
| `guard snapshoot` | Menandai kondisi project saat ini sebagai kondisi aman |
| `guard check` | Mengecek apakah project berubah dari snapshoot terakhir |
| `guard config` | Menyimpan token Discord terenkripsi dan `MUSIC_DIR` |
| `guard run` | Cek workspace, decrypt token, set env, lalu menjalankan bot |

File lokal guard:

- `app/data/workspace_snapshoot.json`
- `app/data/runtime_config.json`

Dua file itu bersifat lokal dan tidak perlu ikut repository.

Alur harian yang disarankan:

```bash
guard config      # pertama kali saja / saat ganti token atau MUSIC_DIR
guard snapshoot   # setelah kondisi project dianggap aman
guard run         # menjalankan bot lewat guard
```

Kalau `guard run` mendeteksi file project berubah, bot tidak akan dijalankan dulu.
Cek perubahannya pakai:

```bash
git status
git diff
```

## File lokal yang dipakai bot

File lokal yang bisa muncul:

- `app/data/autoalir_state.json`
- `app/data/local_cnfg.json`
- `app/data/workspace_snapshoot.json`
- `app/data/runtime_config.json`

File-file itu dipakai untuk state lokal, config lokal, snapshoot workspace, dan config guard.
Semuanya tidak perlu ikut Git.

Kalau jalan langsung lewat `python main.py`, bot masih bisa bikin `local_cnfg.json` dari setup interaktif.
Kalau jalan lewat guard, yang dipakai guard adalah `runtime_config.json`.

## Command yang ada

### Voice

| Command | Fungsi |
| --- | --- |
| `!join` | Bot masuk ke voice channel user |
| `!leave` | Bot keluar dari voice channel |

### Musik lokal & library

| Command | Fungsi |
| --- | --- |
| `!play <judul/path>` | Putar atau tambahkan lagu lokal ke queue |
| `!search <judul>` | Cari lagu lokal |
| `!pick <nomor>` | Putar hasil pencarian |
| `!library` | Buka library musik |
| `!library <halaman>` | Buka library pada halaman tertentu |
| `!open <nomor>` | Buka folder atau putar item yang terlihat |
| `!back` | Balik ke folder library sebelumnya |
| `!refresh` | Refresh cache musik |

### Playback & queue

| Command | Fungsi |
| --- | --- |
| `!queue` | Lihat daftar antrian |
| `!pause` | Pause lagu |
| `!resume` | Lanjutkan lagu |
| `!next` | Skip lagu |
| `!repeat` | Toggle repeat |
| `!shuffle` | Toggle shuffle queue |
| `!remove <angka/nama>` | Hapus item dari queue |
| `!clear` | Kosongkan queue |
| `!now` | Lihat lagu yang sedang diputar |
| `!volume <0-100>` | Atur volume bot |

### Online

| Command | Fungsi |
| --- | --- |
| `!yt <judul>` | Cari dan putar lagu dari YouTube |

### Autoalir

| Command | Fungsi |
| --- | --- |
| `!autoalir on` | Nyalakan autoalir |
| `!autoalir off` | Matikan autoalir |

### Bantuan

| Command | Fungsi |
| --- | --- |
| `!help` | Tampilkan daftar command |
| `!help <command>` | Tampilkan detail satu command |

## Requirement

Yang penting ada ini:

- Python 3.11+ aman
- FFmpeg
- Discord bot token
- Folder musik lokal

Library Python yang kepakai di code sekarang:

- `discord.py`
- `yt-dlp`
- `mutagen`

Kalau mau install cepat, tinggal pakai file requirement yang ada di repo.

## Cara jalanin

### Opsi 1: pakai env var

#### Windows PowerShell

```powershell
$env:DISCORD_TOKEN="YOUR_TOKEN"
$env:MUSIC_DIR="D:\Music"
$env:FFMPEG_PATH="C:\ffmpeg\bin\ffmpeg.exe"  # opsional
python main.py
```

#### Linux / macOS

```bash
export DISCORD_TOKEN="YOUR_TOKEN"
export MUSIC_DIR="$HOME/Music"
export FFMPEG_PATH="/usr/bin/ffmpeg"   # opsional
python3 main.py
```

### Opsi 2: biarin bot nanya sendiri

Kalau `DISCORD_TOKEN` atau `MUSIC_DIR` belum ada, bot bakal minta input waktu start.
Hasilnya nanti disimpan ke `app/data/local_cnfg.json`.

Jalankan aja:

```bash
python main.py
```

### Opsi 3: pakai guard launcher

Build guard dulu.

#### Windows PowerShell

```powershell
go build -o guard.exe .\tools\guard
.\guard.exe config
.\guard.exe snapshoot
.\guard.exe run
```

#### Linux / macOS

```bash
go build -o guard ./tools/guard
./guard config
./guard snapshoot
./guard run
```

Opsi ini yang paling disarankan kalau token ingin disimpan terenkripsi secara lokal.

## Struktur modul singkat

Bagian pentingnya gini:

- `main.py`  
  Entry point bot

- `app/config.py`  
  Ambil config env + config lokal + setup interaktif

- `app/events.py`  
  Event bot, preload cache, cleanup voice, load state autoalir

- `app/player.py`  
  Alur play utama, queue, autoalir, after-play callback

- `app/music_cache.py`  
  Scan folder musik dan fuzzy search

- `app/metadata.py`  
  Baca metadata audio dan cover

- `app/autoalir_store.py`  
  Simpan / load state autoalir ke JSON

- `app/commands/`  
  Semua command Discord

## Catatan

- Cache musik dianggap basi setelah `30` detik
- Bot preload metadata dan cover pelan-pelan saat startup
- State autoalir disimpan lokal, jadi selera dan history bisa kebawa ke restart berikutnya
- Kalau folder musik kosong, bot tetap bisa start, tapi command lokal ya belum ada isinya
