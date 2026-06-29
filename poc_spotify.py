import os
import sys

try:
    from spotify_scraper import SpotifyClient
except ImportError:
    print("pip install spotifyscraper dulu")
    sys.exit(1)


def buat_client():
    sp_dc = os.getenv("SPOTIFY_SP_DC")
    if not sp_dc:
        print(
            "set dulu: export SPOTIFY_SP_DC='AQB...' (atau $env:SPOTIFY_SP_DC='AQB...' di PowerShell)"
        )
        sys.exit(1)
    return SpotifyClient(cookies={"sp_dc": sp_dc})


def _artist_str(track):
    nama = [a.name for a in (track.artists or []) if getattr(a, "name", None)]
    return ", ".join(nama) if nama else "Unknown"


def cari_track(client, query):
    r = client.search(query)
    tracks = r.tracks
    if not tracks:
        return None
    t = tracks[0]
    return (t.name, _artist_str(t), t.duration_ms)


def resolve(client, url):
    if "/track/" in url:
        t = client.get_track(url)
        return [(t.name, _artist_str(t), t.duration_ms)], t.name

    if "/playlist/" in url:
        pl = client.get_playlist(url)
        tracks = [pt.track for pt in pl.tracks if pt.track]
        out = [(t.name, _artist_str(t), t.duration_ms) for t in tracks if t.name]
        return out, pl.name

    if "/album/" in url:
        al = client.get_album(url)
        out = [(t.name, _artist_str(t), t.duration_ms) for t in al.tracks if t.name]
        return out, al.name

    raise ValueError("link bukan track/playlist/album spotify")


if __name__ == "__main__":
    client = buat_client()

    print("--- Tes cari_track ---")
    try:
        hasil = cari_track(client, "melukis senja")
        print("cari_track:", hasil)
    except Exception as e:
        print(f"[ERROR cari_track] {type(e).__name__}: {e}")

    if len(sys.argv) < 2:
        print('\npakai: python poc_spotify.py "<link spotify>"')
        sys.exit(0)

    url = sys.argv[1]

    if "spotify.com" not in url and "spotify:" not in url:
        print(f"\n[INFO] Argumen '{url}' bukan link Spotify, tes selesai.")
        sys.exit(0)

    try:
        items, judul = resolve(client, url)
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"\n=== {judul} ({len(items)} lagu) ===")

    for i, (nama, artist, dur) in enumerate(items[:30], 1):
        menit, detik = divmod(int(dur or 0) // 1000, 60)
        print(f"{i:2}. {nama} — {artist} ({menit}:{detik:02d})")

    if len(items) > 30:
        print(f"... +{len(items) - 30} lagi")
