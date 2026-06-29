import requests

BASE = "https://lrclib.net/api"
HEADERS = {"User-Agent": "bot-music PoC (https://github.com/Iphants/bot-music)"}


def get_exact(judul, artist, durasi, album=None):
    params = {
        "track_name": judul,
        "artist_name": artist,
        "duration": int(durasi),
    }
    if album:
        params["album_name"] = album
    r = requests.get(f"{BASE}/get", params=params, headers=HEADERS, timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def search(judul, artist=None):
    params = {"track_name": judul}
    if artist:
        params["artist_name"] = artist
    r = requests.get(f"{BASE}/search", params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def ambil_lirik(judul, artist, durasi, album=None):
    hit = get_exact(judul, artist, durasi, album)
    if hit:
        return hit, "exact"

    hasil = search(judul, artist)
    if not hasil:
        return None, "kosong"

    if durasi:
        hasil.sort(key=lambda x: abs((x.get("duration") or 0) - durasi))

    return hasil[0], "search"


def _ringkas(data):
    synced = data.get("syncedLyrics")
    plain = data.get("plainLyrics")
    if synced:
        baris = synced.strip().splitlines()
        return f"SYNCED, {len(baris)} baris\n  contoh: {baris[0] if baris else '-'}"
    if plain:
        baris = plain.strip().splitlines()
        return f"PLAIN (no timestamp), {len(baris)} baris\n  contoh: {baris[0] if baris else '-'}"
    return "ketemu tapi instrumental / lirik kosong"


if __name__ == "__main__":
    tes = [
        ("Idol", "YOASOBI", 206),
        ("Shoujo Rei", "Mafumafu", 291),
        ("lagu ngaco yang ga ada", "siapa tau", 180),
    ]

    for judul, artist, durasi in tes:
        print(f"\n=== {judul} - {artist} ({durasi}s) ===")
        try:
            data, asal = ambil_lirik(judul, artist, durasi)
        except requests.RequestException as e:
            print(f"  [ERROR] request gagal: {e}")
            continue
        if not data:
            print("  ga ketemu")
            continue
        print(f"  match via: {asal}")
        print(
            f"  hasil: {data.get('trackName')} - {data.get('artistName')} "
            f"({data.get('duration')}s)"
        )
        print(" ", _ringkas(data))
