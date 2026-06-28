# Change Plan: `!now` dan `!queue`

Rencana ini dibagi jadi tiga bagian:

1. Beresin nama lagu supaya tidak muncul angka dobel.
2. Upgrade `!queue` jadi embed + pagination.
3. Tambah progress / waktu berjalan di `!now`.

Tahap 1 dan 2 relatif aman karena mostly command display.
Tahap 3 lebih hati-hati karena mulai nyentuh state playback.

## Masalah 1: angka dobel di output Discord

Contoh yang muncul sekarang:

```text
1. 1. Love material.flac
2. 1 Sakura Biyori
```

Itu terjadi karena nomor pertama dari bot, lalu nama file lokal juga masih punya nomor track.
Misalnya file asli:

```text
01. Love material.flac
1 Sakura Biyori.flac
```

Target tampilannya:

```text
1. Love material
2. Sakura Biyori
```

Jadi helper nama antrean perlu bersihin:

- nomor track di depan
- ekstensi file
- underscore jadi spasi
- spasi berlebihan

## File yang perlu diubah

Tahap 1 dan 2:

- `app/commands/playback.py`
- `app/commands/queue_cmds.py`

Tahap 3:

- `app/state.py`
- `app/player.py`
- `app/commands/playback.py`

## Urutan perubahan

1. Rapihin helper nama queue dulu.
2. Pakai helper itu di `!now`.
3. Upgrade `!queue` jadi embed pagination, sumbernya `state.play_queue`.
4. Baru setelah tampilan aman, tambah state progress.
5. Set progress saat lagu benar-benar mulai.
6. Update pause / resume supaya progress tidak jalan saat pause.
7. Tampilkan progress di `!now`.

## Tahap 1: helper nama antrean

### `app/commands/playback.py`

Patch kecil: ganti helper `_nama_queue(item)` supaya output lokal lebih bersih.

```python
def _nama_queue(item):
    if isinstance(item, dict):
        return item.get("title", "Unknown YouTube")

    nama = os.path.basename(str(item))
    nama = os.path.splitext(nama)[0]
    nama = nama.replace("_", " ")
    nama = re.sub(r"^\s*\d+\s*[\.\-_\)\]]*\s*", "", nama)
    nama = re.sub(r"\s+", " ", nama).strip()
    return nama or os.path.basename(str(item))
```

Alasan:

- `!now` dan `!queue` sama-sama butuh nama item yang rapi.
- Ini langsung ngilangin kasus `1. 01. Lagu.flac`.
- Untuk YouTube tetap ambil `title` dari dict.

Catatan:

- Helper ini bisa tetap di `playback.py`, lalu `queue_cmds.py` import dari sana.
- Kalau tidak mau import silang, helper serupa bisa ditaruh di `queue_cmds.py` dulu. Sedikit duplikasi masih oke.

## Tahap 2: upgrade `!queue` jadi embed + pagination

Sekarang `!queue` masih teks biasa dan pakai `state.queue_asli`.
Untuk tampilan baru, lebih enak pakai `state.play_queue`.

Alasannya:

- `play_queue` adalah antrean yang benar-benar akan diputar berikutnya.
- Kalau shuffle aktif, `play_queue` berubah.
- `queue_asli` tetap berguna sebagai urutan asli dan buat balikin shuffle.

Jadi `!queue` harus menjawab:

> habis ini lagu apa?

Bukan:

> dulu user masukin lagunya urutan apa?

### `app/commands/queue_cmds.py`

Patch 1: ubah signature command supaya bisa ambil halaman.

```python
    @bot.command()
    async def queue(ctx, page: int = 1):
```

Alasan:

- `!queue` default halaman 1.
- `!queue 2` buka halaman 2.
- Tidak perlu tombol dulu. Tombol bisa nanti.

Patch 2: pakai embed pagination 10 item per halaman.

```python
    @bot.command()
    async def queue(ctx, page: int = 1):
        guild_id = ctx.guild.id
        per_page = 10

        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)

            daftar = list(state.play_queue.get(guild_id, []))
            current = state.current_playing.get(guild_id)

            if not current and not daftar:
                return await ctx.send("Antrean kosong")

            total = len(daftar)
            max_page = max(1, (total - 1) // per_page + 1)
            page = max(1, min(page, max_page))

            start = (page - 1) * per_page
            end = start + per_page
            potongan = daftar[start:end]

            embed = discord.Embed(
                title="Antrean Musik",
                color=0x41639b,
            )

            if isinstance(current, dict):
                now_txt = current.get("title", "Unknown YouTube")
                uploader = current.get("uploader")
                if uploader:
                    now_txt += f" — {uploader}"
            elif current:
                now_txt = _nama_queue(current)
            else:
                now_txt = "Tidak ada lagu yang sedang diputar"

            embed.description = f"Lagi diputar:\n{now_txt}"

            lines = []
            for idx, item in enumerate(potongan, start=start + 1):
                lines.append(f"{idx}. {_nama_queue(item)}")

            embed.add_field(
                name="Berikutnya",
                value="\n".join(lines) if lines else "(kosong)",
                inline=False,
            )

            footer = f"Halaman {page}/{max_page} • Total {total} lagu"
            if state.is_shuffle.get(guild_id, False):
                footer += " • Shuffle aktif"
            embed.set_footer(text=footer)

            await ctx.send(embed=embed)
```

Alasan:

- 10 item per halaman cukup lega.
- `!now` tetap preview 5 item.
- `!queue` jadi tempat lihat antrean panjang.
- Field queue dibuat full-width, bukan inline.
- Footer kasih info halaman, total, dan shuffle.

Catatan kecil:

- Kalau queue kosong tapi ada lagu sedang diputar, embed tetap muncul.
- Kalau queue kosong dan tidak ada current, cukup kirim `Antrean kosong`.

## Tahap 3: progress bar / waktu berjalan di `!now`

Ini fitur yang lebih dalam.
Bot harus tahu lagu mula ijam berapa.

State yang perlu ditambah:

### `app/state.py`

Patch kecil:

```python
started_at = {}
paused_at = {}
total_paused = {}
```

Arti:

- `started_at[guild_id]`: waktu lagu mulai
- `paused_at[guild_id]`: waktu user mulai pause
- `total_paused[guild_id]`: total waktu pause untuk lagu sekarang

## Set waktu mulai lagu

Waktu mulai harus di-set setelah `voice_client.play(...)` sukses.
Jangan set sebelum play, supaya lagu gagal play tidak dianggap mulai.

### `app/commands/playback.py`

Jalur `!play` langsung saat bot kosong:

```python
voice_client.play(source, after=partial(player.after_play, guild_id, voice_client))
state.started_at[guild_id] = time.time()
state.paused_at.pop(guild_id, None)
state.total_paused[guild_id] = 0
player.catat_selera(guild_id, file_rel_path)
```

Jalur `!yt` langsung saat bot kosong:

```python
voice_client.play(source, after=partial(player.after_play, guild_id, voice_client))
state.started_at[guild_id] = time.time()
state.paused_at.pop(guild_id, None)
state.total_paused[guild_id] = 0
state.current_playing[guild_id] = yt_item
```

Alasan:

- `!play` dan `!yt` punya jalur direct play sendiri.
- Kalau bot sedang kosong, lagu tidak lewat `play_next()`.

### `app/player.py`

Jalur lagu berikutnya dari queue, di `play_next()` setelah `voice_client.play(...)` sukses:

```python
voice_client.play(source, after=partial(after_play, guild_id, voice_client))
state.started_at[guild_id] = time.time()
state.paused_at.pop(guild_id, None)
state.total_paused[guild_id] = 0
```

Ini perlu ditaruh di dua cabang:

- YouTube dict
- file lokal

Jalur repeat, di `replay_c()` setelah `voice_client.play(...)`:

```python
voice_client.play(source, after=partial(after_play, guild_id, voice_client))
state.started_at[guild_id] = time.time()
state.paused_at.pop(guild_id, None)
state.total_paused[guild_id] = 0
```

Alasan:

- Repeat berarti lagu mulai lagi dari awal.
- Progress harus balik ke `0:00`.

## Pause dan resume

### `app/commands/playback.py`

Di `pause`, setelah `voice_client.pause()`:

```python
if guild_id not in state.paused_at:
    state.paused_at[guild_id] = time.time()
```

Di `resume`, setelah `voice_client.resume()`:

```python
paused = state.paused_at.pop(guild_id, None)
if paused:
    state.total_paused[guild_id] = state.total_paused.get(guild_id, 0) + (time.time() - paused)
```

Alasan:

- Kalau lagu dipause 5 menit, progress tidak boleh ikut maju 5 menit.
- Saat pause, elapsed dihitung sampai titik pause.

## Hitung elapsed untuk `!now`

Helper kecil di `app/commands/playback.py`:

```python
def _elapsed_lagu(guild_id):
    mulai = state.started_at.get(guild_id)
    if not mulai:
        return None

    total_pause = state.total_paused.get(guild_id, 0)
    if guild_id in state.paused_at:
        return max(0, state.paused_at[guild_id] - mulai - total_pause)
    return max(0, time.time() - mulai - total_pause)
```

Helper progress bar:

```python
def _progress_bar(elapsed, duration, lebar=10):
    if not elapsed or not duration:
        return None

    ratio = min(1, max(0, elapsed / duration))
    isi = int(ratio * lebar)
    return "▰" * isi + "▱" * (lebar - isi)
```

Catatan:

- Kalau durasi kosong, jangan paksa progress.
- Kalau elapsed kosong, tampilkan durasi total saja.

## Update layout `!now`

Bentuk akhir yang enak:

```text
Lagi Play

Love material
oleh MORE MORE JUMP!
Album Love material / icedrop              [cover]

━━━━━━━━━━━━

Antrean berikutnya
1. Sakura Biyori and Time Machine...
2. Sakura Biyori and Time Machine...
3. Hated by Life Itself...
4. Melt...
5. World is Mine...
+ 35 lagu lagi

Progress
1:12 / 4:38
▰▰▰▱▱▱▱▱▱▱

Antrean: 40 lagu • Shuffle aktif
```

Patch di `!now`:

```python
elapsed = _elapsed_lagu(guild_id)
bar = _progress_bar(elapsed, duration)

if elapsed is not None and duration:
    progress_txt = f"{_fmt_durasi(elapsed)} / {_fmt_durasi(duration)}"
    if bar:
        progress_txt += f"\n{bar}"
else:
    progress_txt = f"Durasi: {_fmt_durasi(duration)}"

embed.add_field(name="Progress", value=progress_txt, inline=False)

footer = f"Antrean: {len(queue_now)} lagu"
if state.is_shuffle.get(guild_id, False):
    footer += " • Shuffle aktif"
embed.set_footer(text=footer)
```

Alasan:

- Queue tetap full-width.
- Progress juga full-width.
- Footer cuma info kecil: total antrean dan shuffle.
- Durasi tidak rebutan tempat dengan queue.

## Yang jangan dilakukan dulu

- Jangan bikin tombol pagination dulu.
- Jangan pakai `queue_asli` untuk tampilan `!queue`.
- Jangan set `started_at` sebelum `voice_client.play(...)` sukses.
- Jangan bikin progress palsu kalau durasi kosong.
- Jangan ubah `player.py` selain titik yang memang mulai playback.

## Bagian yang perlu dites

### Tes nama queue

```text
!play 01. Love material.flac
!play 1 Sakura Biyori.flac
!now
!queue
```

Yang dicek:

- tidak ada `1. 1.`
- ekstensi file tidak tampil
- nomor track depan hilang

### Tes queue pagination

```text
!play lagu1
!play lagu2
...
!play lagu15
!queue
!queue 2
```

Yang dicek:

- halaman 1 berisi 1 sampai 10
- halaman 2 berisi 11 sampai 15
- footer benar: `Halaman 1/2 • Total 15 lagu`

### Tes shuffle

```text
!shuffle
!queue
```

Yang dicek:

- urutan mengikuti `play_queue`
- footer menampilkan `Shuffle aktif`

### Tes progress lokal

```text
!play lagu
!now
```

Tunggu 10 detik, lalu:

```text
!now
```

Yang dicek:

- elapsed naik
- total durasi tetap
- progress bar berubah

### Tes pause resume

```text
!pause
```

Tunggu 10 detik, lalu:

```text
!now
```

Yang dicek:

- elapsed tidak lanjut jauh saat pause

Lalu:

```text
!resume
!now
```

Yang dicek:

- elapsed lanjut dari posisi sebelum pause

### Tes YouTube

```text
!yt judul lagu
!now
```

Yang dicek:

- thumbnail muncul
- uploader muncul
- progress jalan kalau duration tersedia
