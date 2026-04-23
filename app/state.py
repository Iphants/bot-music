from __future__ import annotations

# ===== PLAYBACK STATE =====
is_shuffle = {}
current_playing = {}
file_cache = {}
cache_timestamp = 0.0
tingkat_suara = {}
ulang_lagu = {}

# ===== QUEUE STATE =====
kunci_guild = {}
flag_shuffle = {}
queue_asli = {}
play_queue = {}
gabut = {}

# ===== UI & CACHE STATE =====
last_search = {}
folder_terakhir = {}
metadata_cache = {}
cover_cache = {}
folder_history = {}
cache_preload_started = False

# ===== AUTOALIR STATE =====
mode_autoalir = {}
selera_guild = {}
lagu_terakhir_lokal = {}
debug_autoalir = True
history_autoalir = {}
history_mid_autoalir = {}
history_jdul_autoalir = {}
autoalir_state_loaded = False