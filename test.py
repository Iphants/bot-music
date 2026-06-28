import asyncio
import os
os.environ.setdefault("MUSIC_DIR", r"E:\Music")

import app.state as state
state.debug_autoalir = False
from app import cover_cache, config

root = config.music_root_dir()

# ambil 1 file .flac pertama yang ketemu, relatif ke MUSIC_DIR
lagu_rel = None
for p in root.rglob("*.flac"):
    lagu_rel = p.relative_to(root).as_posix()
    break

print("file ketemu:", lagu_rel)

async def main():
    if not lagu_rel:
        print("ga nemu .flac sama sekali, cek MUSIC_DIR")
        return

    full = root / lagu_rel
    print("full path ada?", full.exists())

    b, fn = cover_cache._ekstra_cover(full)
    print("cover kebaca?", b is not None, "| ukuran:", len(b) if b else 0, "bytes")

    print("\n=== resolve (upload beneran) ===")
    url = await cover_cache.resolve_cover(lagu_rel)
    print("url:", url)

asyncio.run(main())