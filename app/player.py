from __future__ import annotations
import asyncio
import os
import random
from collections import deque
from functools import partial
from random import shuffle as sf
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from . import config
from . import runtime
from . import state

def kunci_lagu(guild_id):
    if guild_id not in state.kunci_guild:
        state.kunci_guild[guild_id] = asyncio.Lock()
    return state.kunci_guild[guild_id]

def shuffle_queue(guild_id):
    q = state.play_queue.get(guild_id)
    if not q or len(q) <= 1:
        return
    
    temp = list(q)
    random.shuffle(temp)
    state.play_queue[guild_id] = deque (temp)

def shuffle_internal(guild_id):
    q = list(state.play_queue[guild_id])
    if len(q) <= 1:
        return
    kepala = q[0]
    ekor = q[1:]
    random.shuffle(ekor)
    state.play_queue[guild_id] = deque([kepala] + ekor)

def ensure_deques(guild_id):
    if guild_id not in state.queue_asli:
        state.queue_asli[guild_id] = deque()
    if guild_id not in state.play_queue:
        state.play_queue[guild_id] = deque()

def after_play(guild_id, voice_client, error):
    if error:
        print(f"error pas mainin (guild {guild_id}): {error}")
    try:
        if state.ulang_lagu.get(guild_id, False):
            lagu = state.current_playing.get(guild_id)
            if isinstance (lagu, dict):
                src = FFmpegPCMAudio(
                    source = lagu["url"],
                    executable = config.ffmpeg_executable(),
                    options = "-vn -loglevel panic",
                )
            else:
                path = config.music_root_dir() / lagu
                src = FFmpegPCMAudio(
                    source = str(path),
                    executable = config.ffmpeg_executable(),
                    options = "-vn -loglevel panic",
                )
            vol = state.tingkat_suara.get(guild_id, 0.5)
            source = PCMVolumeTransformer(src, volume=vol)
            voice_client.play(
                source,
                after=partial(after_play, guild_id, voice_client)
            )
            return
        if state.flag_shuffle.get(guild_id, False):
            shuffle_queue(guild_id)

        def _log_done(fut):
            try:
                fut.result()
            except Exception as e:
                print(f"play_next future error (guild{guild_id}): {e}")

        try:
            bot_loop = runtime.get_bot_loop()
        except Exception:
            bot_loop = None

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if bot_loop is not None and running_loop is not bot_loop:
            future = asyncio.run_coroutine_threadsafe(play_next(guild_id, voice_client), bot_loop)
            future.add_done_callback(_log_done)
        else:
            # either we're already in the bot loop, or bot_loop isn't available
            if running_loop is not None:
                asyncio.create_task(play_next(guild_id, voice_client))
            elif bot_loop is not None:
                future = asyncio.run_coroutine_threadsafe(play_next(guild_id, voice_client), bot_loop)
                future.add_done_callback(_log_done)
            else:
                # last resort: try default event loop
                loop = asyncio.get_event_loop()
                future = asyncio.run_coroutine_threadsafe(play_next(guild_id, voice_client), loop)
                future.add_done_callback(_log_done)

    except Exception as e:
        print (f"after_play handler error {e}")
        state.current_playing.pop(guild_id, None)            

async def play_next(guild_id, voice_client):
    if not voice_client or not voice_client.is_connected():
        state.current_playing.pop(guild_id, None)
        state.queue_asli.pop(guild_id, None)
        state.play_queue.pop(guild_id, None)
        return

    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)

        if not state.play_queue.get(guild_id) or len(state.play_queue[guild_id]) == 0:
            print(f"antrian kosong jir untuk guild {guild_id}")
            return

        while state.play_queue[guild_id]:
            item = state.play_queue[guild_id].popleft()

            try:
                if item in state.queue_asli.get(guild_id, []):
                    state.queue_asli[guild_id].remove(item)
            except ValueError:
                pass

            try:
                if isinstance(item, dict):
                    stream_url = item["url"]
                    title = item["title"]

                    state.current_playing[guild_id] = item

                    src = FFmpegPCMAudio(
                        source=stream_url,
                        executable=config.ffmpeg_executable(),
                        options="-vn -loglevel panic",
                    )
                    vol = state.tingkat_suara.get(guild_id, 0.5)
                    source = PCMVolumeTransformer(src, volume=vol)

                    voice_client.play(
                        source,
                        after=partial(after_play, guild_id, voice_client)
                    )
                    print(f"Now playing YT: {title}")
                    return

                file_rel_path = item
                path_full = config.music_root_dir() / file_rel_path

                if not path_full.exists():
                    print(f"file ilang, nooo:{path_full}")
                    continue

                state.current_playing[guild_id] = file_rel_path

                src = FFmpegPCMAudio(
                    source=str(path_full),
                    executable=config.ffmpeg_executable(),
                    options="-vn -loglevel panic",
                )
                vol = state.tingkat_suara.get(guild_id, 0.5)
                source = PCMVolumeTransformer(src, volume=vol)

                voice_client.play(
                    source,
                    after=partial(after_play, guild_id, voice_client)
                )
                return

            except Exception as e:
                print(f"Gagal ngeplay item berikutnya: {e}")
                state.current_playing.pop(guild_id, None)
                continue

    state.current_playing.pop(guild_id, None)
    print("gada lagu yang valid yang bisa di puter jir")