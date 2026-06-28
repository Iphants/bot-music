from __future__ import annotations

# state yang kepake pas lagu lagi diputer
is_shuffle = {}
current_playing = {}
file_cache = {}
cache_timestamp = 0.0
tingkat_suara = {}
ulang_lagu = {}
started_at = {}
paused_at = {}
total_pause = {}

# state antrian per guild
kunci_guild = {}
flag_shuffle = {}
queue_asli = {}
play_queue = {}
gabut = {}


# state buat ui kecil-kecilan sama cache
last_search = {}
folder_terakhir = {}
metadata_cache = {}
cover_cache = {}
folder_history = {}
cache_preload_started = False

# state yang nyimpen kebiasaan autoalir
mode_autoalir = {}
selera_guild = {}
lagu_terakhir_lokal = {}
debug_autoalir = True
history_autoalir = {}
history_mid_autoalir = {}
history_jdul_autoalir = {}
autoalir_state_loaded = False

# dashboard now-playing yang di-edit
last_np_message = {}
pesan_sejak_np = {}
np_channel = {}