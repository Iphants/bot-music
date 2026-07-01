from __future__ import annotations
from . import config

try:
    from spotify_scraper import SpotifyClient
except ImportError:
    SpotifyClient = None

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if SpotifyClient is None:
        return None
    sp_dc = config.spotify_sp_dc()
    if not sp_dc:
        return None
    _client = SpotifyClient(cookies={"sp_dc": sp_dc})
    return _client


def aktif() -> bool:
    return _get_client() is not None


def _artist_str(track) -> str:
    nama = [a.name for a in (track.artists or []) if getattr(a, "name", None)]
    return ", ".join(nama) if nama else "Unknown"


def cari_track(query: str):
    client = _get_client()
    if not client:
        return None
    try:
        r = client.search(query)
        tracks = r.tracks
        if not tracks:
            return None
        t = tracks[0]
        return (t.name, _artist_str(t), t.duration_ms, _cover_url(t), _album_name(t))
    except Exception as e:
        print(f"[SPOTIFY] cari_track gagal: {e}")
        return None


def resolve(url: str):
    client = _get_client()
    if not client:
        return None, []
    try:
        if "/track/" in url:
            t = client.get_track(url)
            return t.name, [
                (t.name, _artist_str(t), t.duration_ms, _cover_url(t), _album_name(t))
            ]
        if "/playlist/" in url:
            pl = client.get_playlist(url)
            tracks = [pt.track for pt in pl.tracks if pt.track]
            out = [
                (t.name, _artist_str(t), t.duration_ms, _cover_url(t), _album_name(t))
                for t in tracks
                if t.name
            ]
            return pl.name, out
        if "/album/" in url:
            al = client.get_album(url)
            al_cover = _cover_url(al)
            out = []
            for t in al.tracks:
                if not t.name:
                    continue
                cov = _cover_url(t) or al_cover
                out.append((t.name, _artist_str(t), t.duration_ms, cov, al.name))
            return al.name, out
    except Exception as e:
        print(f"[SPOTIFY] resolve gagal: {e}")
    return None, []


def _cover_url(track) -> str | None:
    imgs = getattr(track, "images", None) or []
    if not imgs:
        return None
    best = max(imgs, key=lambda im: getattr(im, "width", 0) or 0)
    return getattr(best, "url", None)


def _album_name(track) -> str | None:
    al = getattr(track, "album", None)
    return getattr(al, "name", None) if al else None
