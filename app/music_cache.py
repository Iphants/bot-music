from __future__ import annotations
import difflib
import os
import time
from . import config
from . import state

def buat_music_cache():
    music_files = {}
    ekstensi_valid = (".mp3", ".wav", ".flac", ".m4a")
    root_dir = config.music_root_dir()
    try:
        for root, _, files in os.walk(root_dir):
            for file in files:
                if not file.lower().endswith(ekstensi_valid):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir)
                katkunc_nama = file.lower()
                # normalize separators so stored rel paths work across OS
                katkunc_rel = rel_path.replace(os.sep, "/").lower()
                rel_path_norm = rel_path.replace(os.sep, "/")
                music_files.setdefault(katkunc_nama, []).append(rel_path_norm)
                music_files.setdefault(katkunc_rel, []).append(rel_path_norm)
        print(f"isi cache:{len(music_files)} entries")
        return music_files
    except Exception as e:
        print(f"error ngebangun cache {e}")
        return {}

def dapetin_cache_file():
    sekarang = time.time()
    if not state.file_cache or (sekarang - state.cache_timestamp > config.CACHE_DURATION_SECONDS):
        state.file_cache = buat_music_cache()
        state.cache_timestamp = sekarang
    return state.file_cache

def cari_lagu(query):
    try:
        semua_file_cache = dapetin_cache_file()
        query_lower = query.lower()
        if query_lower in semua_file_cache:
            return semua_file_cache[query_lower].copy()
        semua_katkunc = list(semua_file_cache.keys())
        hasil_fuzzy = difflib.get_close_matches(query_lower, semua_katkunc, n=20, cutoff=0.5)
        semua_hasil = []
        for key in hasil_fuzzy:
            semua_hasil.extend(semua_file_cache.get(key, []))
        seen = set()
        out = []
        for item in semua_hasil:
            if item not in seen:
                seen.add(item)
                out.append(item)
            if len(out) >= 20:
                break
        return out
    except Exception as e:
        print(f"error jir ngebaca direktori nya: {e}")
        return []

def cari_file_cocok(nama_file):
    try:
        semua_file_cache = dapetin_cache_file()
        nama_file_lower = nama_file.lower().strip()
        if nama_file_lower in semua_file_cache:
            return semua_file_cache[nama_file_lower][0]
        qnorm = nama_file_lower.replace("\\", "/")
        if qnorm in semua_file_cache:
            return semua_file_cache[qnorm][0]
        if not any(nama_file_lower.endswith(ext) for ext in (".mp3", ".wav", ".flac", ".m4a")):
            for ext in (".flac", ".mp3", ".wav", ".m4a"):
                nama_file_ext = nama_file_lower + ext
                if nama_file_ext in semua_file_cache:
                    return semua_file_cache[nama_file_ext][0]
        for key in semua_file_cache.keys():
            if nama_file_lower in key:
                return semua_file_cache[key][0]
        hasil_fuzzy = cari_lagu(nama_file)
        if hasil_fuzzy:
            return hasil_fuzzy[0]
        return None
    except Exception as e:
        print(f"Error nyari file nya jir: {e}")
        return None
