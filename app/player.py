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
from .yt import get_audio_source

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

def build_audio(source, volume=0.5):
    before_options = ""
    options = "-vn -loglevel panic"
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        before_options += " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    src = FFmpegPCMAudio(source=source, executable=config.ffmpeg_executable(), before_options=before_options, options=options)
    return PCMVolumeTransformer(src, volume=volume)
def cancel_idle_leave(guild_id):
    task = state.gabut.pop(guild_id, None)
    if task and not task.done ():
        task.cancel()

def schedule_leave(guild_id, voice_client, delay = 15 * 60):
    cancel_idle_leave(guild_id)        

    async def _job():
        try:
            await asyncio.sleep(delay)   
            if not voice_client or not voice_client.is_connected():
                return
            if voice_client.is_playing() or voice_client.is_paused():
                return
            state.queue_asli.pop(guild_id, None)
            state.play_queue.pop(guild_id, None)
            state.current_playing.pop(guild_id,  None)
            await voice_client.disconnect()
            print(f"Bot auto keluar voice karena idle {guild_id}")
        except asyncio.CancelledError:
            pass
        finally:
            if state.gabut.get(guild_id) is asyncio.current_task():
                state.gabut.pop(guild_id, None)

    state.gabut[guild_id] = asyncio.create_task(_job())

async def replay_c(guild_id, voice_client):
    async with kunci_lagu(guild_id):
        lagu = state.current_playing.get(guild_id)
        if not lagu or not voice_client or not voice_client.is_connected():
            return
        vol = state.tingkat_suara.get(guild_id, 0.5)
        if isinstance (lagu, dict):
            fresh = await get_audio_source(lagu["webpage_url"])
            source = build_audio(fresh["url"], volume=vol)
        else:
            source = build_audio(str(config.music_root_dir() / lagu), volume=vol)

        voice_client.play(source, after=partial(after_play, guild_id, voice_client))


def after_play(guild_id, voice_client, error):
    if error:
        print(f"[ERROR STREAM] guild {guild_id} error saat play: {error}")
        return
    try:
        if state.ulang_lagu.get(guild_id, False):
            loop = runtime.get_bot_loop()
            asyncio.run_coroutine_threadsafe(replay_c(guild_id, voice_client), loop)
            return
        if state.flag_shuffle.get(guild_id, False):
            shuffle_queue(guild_id)

        state.current_playing.pop(guild_id, None)
        loop = runtime.get_bot_loop()
        asyncio.run_coroutine_threadsafe(play_next(guild_id, voice_client), loop)

    except Exception as e:
        print (f"after_play handler error {e}")
        state.current_playing.pop(guild_id, None)            

async def play_next(guild_id, voice_client):
    if not voice_client or not voice_client.is_connected():  
        state.current_playing.pop(guild_id, None)  
        return  

    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)

        if not state.play_queue.get(guild_id) or len(state.play_queue[guild_id]) == 0:
            print(f"antrian kosong jir untuk guild {guild_id}")
            schedule_leave(guild_id, voice_client)
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
                    title = item["title"]
                    state.current_playing[guild_id] = item
                    vol = state.tingkat_suara.get(guild_id, 0.5)
                    fresh = await get_audio_source(item["webpage_url"])
                    source = build_audio(fresh["url"], volume=vol)
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
                vol = state.tingkat_suara.get(guild_id, 0.5)
                source = build_audio(str(path_full), volume=vol)
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