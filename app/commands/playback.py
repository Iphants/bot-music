from __future__ import annotations
import os
import time
import traceback
import discord
import io
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
from .. import config
from .. import music_cache
from .. import player
from .. import state
from ..yt import get_audio_source
from functools import partial
from ..metadata import get_audio_metadata, get_cover

def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def play(ctx, *, nama_file: str):
        voice_client = ctx.voice_client
        if not voice_client:
            await ctx.send("Botnya gada di dalem, pake !join")
            return
        guild_id = ctx.guild.id
        player.cancel_idle_leave(guild_id)

        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            
        file_rel_path = music_cache.cari_file_cocok(nama_file)

        if not file_rel_path:
            hasil_saran = music_cache.cari_lagu(nama_file)
            if hasil_saran:
                saran = "\n".join([f"-{os.path.basename(f)}" for f in hasil_saran[:20]])
                await ctx.send(f"Blom gw tambahin jir {nama_file}, yang ini kah?\n{saran}\n\natau coba cari di youtube?: ketik: !yt {nama_file}")
            else:
                await ctx.send(f"Blom gw tambahin jir {nama_file}, coba cari di youtube?: ketik: !yt {nama_file} ")
                return
            
        file_path_full = config.music_root_dir() / file_rel_path
        if not file_path_full.exists():
            await ctx.send("Musiknya corrupt atau hilang jir")
            return

        is_playing_now = voice_client.is_playing() or voice_client.is_paused() or guild_id in state.current_playing
        if is_playing_now:
            state.queue_asli[guild_id].append(file_rel_path)
            state.play_queue[guild_id].append(file_rel_path)
            posisi = len(state.queue_asli[guild_id])
            metdat = get_audio_metadata(file_path_full)

            if not metdat:
                await ctx.send("gagal baca metadata")
                return
            
            durasi = metdat["duration"]
            menit = durasi // 60
            detik = durasi % 60
            title = (metdat["title"])                         
            artist = metdat["artist"]                       
            album = metdat["album"]                         
            embed = discord.Embed(title=title, description=f"oleh {artist}\nAlbum: {album}", color=0x41639b)                                                           
            embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}", inline=True)   
            embed.add_field(name="Posisi", value=str(posisi), inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True) 
            cover = get_cover(file_path_full)
            
            if cover:
                file = discord.File(fp=io.BytesIO(cover), filename="cover.jpg")
                embed.set_thumbnail(url="attachment://cover.jpg")
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send(embed=embed)
            return

        state.current_playing[guild_id] = file_rel_path
        player.ensure_deques(guild_id)
         
        try:
            state.current_playing[guild_id] = file_rel_path
            volume = state.tingkat_suara.get(guild_id, 0.5)
            source = player.build_audio(str(file_path_full), volume=volume)
            voice_client.play(source, after=partial(player.after_play, guild_id, voice_client))
            metdat = get_audio_metadata(file_path_full)

            if not metdat:
                await ctx.send("gagal baca metadata")
                return
            
            durasi = metdat["duration"]
            menit = durasi //60
            detik = durasi % 60
            title = (metdat["title"])                         
            artist = metdat["artist"]                     
            album = metdat["album"]                       
            embed = discord.Embed(title=title, description=f"oleh {artist}\nAlbum: {album}", color=0x41639b)                                                           
            embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}", inline=True) 
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            cover = get_cover(file_path_full)
            if cover:
                file = discord.File(fp=io.BytesIO(cover), filename="cover.jpg")
                embed.set_thumbnail(url="attachment://cover.jpg")
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send(embed=embed)

        except Exception as e:
            state.current_playing.pop(guild_id, None)
            await ctx.send(f"error anjay {e}")
            print(traceback.format_exc())

    @bot.command()
    async def yt(ctx, *, query: str):
        voice_client = ctx.voice_client
        if not voice_client:
            await ctx.send("Botnya gada di dalem, pake !join")
            return        
        guild_id = ctx.guild.id
        player.cancel_idle_leave(guild_id)
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
        await ctx.send(f"cariin di yt bentar: {query}...")
        try:
            data = await get_audio_source(f"ytsearch:{query}")
        except Exception as e:
            await ctx.send(f"gagal cari di yt: {e}")
            return
        
        if not data or not data.get("webpage_url"):
            await ctx.send("yt error: ga nemu hasilnya")
            return
        
        yt_item = {
            "webpage_url": data["webpage_url"],
            "title": data ["title"],
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader"),
            "duration": data.get("duration"),
            }       
        stream_url = data["url"]
        title = data["title"]
        volume = state.tingkat_suara.get(guild_id, 0.5)
        source = player.build_audio(stream_url, volume=volume)

        if voice_client.is_playing() or voice_client.is_paused():
            player.ensure_deques(guild_id)
            state.queue_asli[guild_id].append(yt_item)
            state.play_queue[guild_id].append(yt_item)
            embed = discord.Embed(title=f"Masuk antiran", description=yt_item["title"], color=0x12d3d3)
            if yt_item.get("thumbnail"):
                embed.set_thumbnail(url=yt_item["thumbnail"])
            if yt_item.get("duration"):
                durasi = yt_item["duration"]
                menit = durasi // 60
                detik = durasi % 60
                embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}") 
            if yt_item.get("webpage_url"):
                embed.add_field(name="Link", value=yt_item["webpage_url"], inline=False)
            await ctx.send(embed=embed)
            
        else:
            voice_client.play(source, after=partial(player.after_play, guild_id, voice_client))
            state.current_playing[guild_id] = yt_item
            embed = discord.Embed(title=yt_item["title"], description = f"oleh {yt_item.get('uploader', 'unknown')}", color=0x12d3d3)

            if yt_item.get("thumbnail"):
                embed.set_thumbnail(url=yt_item["thumbnail"])
            if yt_item.get("duration"):
                durasi = yt_item["duration"]
                menit = durasi // 60
                detik = durasi % 60
                embed.add_field(name="Durasi", value=f"{menit}:{detik:02d}") 
            if yt_item.get("webpage_url"):
                embed.add_field(name="Link", value=yt_item["webpage_url"], inline=False)
            await ctx.send(embed=embed)

    @bot.command()
    async def search(ctx, *, query: str):
        hasil = music_cache.cari_lagu(query)
        if not hasil:
            await ctx.send("Blom gw tambahin jir musiknya")
            return
        format_baris = []
        for i, file_path in enumerate(hasil[:20]):
            nama_file = os.path.basename(file_path)
            folder = os.path.dirname(file_path)
            album = folder.split("/")[-1] if "/" in folder else "Unknown Album"
            format_baris.append(f"{i+1}. {nama_file} [{album}]")

        state.last_search[ctx.author.id] = hasil[:20]
        formatted = "\n".join(format_baris)
        await ctx.send(f"nih ya embut '{query}':\n{formatted}")

    @bot.command()
    async def pick(ctx, nomor: int):
        hasil = state.last_search.get(ctx.author.id)

        if not hasil:
            await ctx.send("lu blom search apa-apa")
            return
        if nomor < 1 or nomor > len(hasil):
            await ctx.send("nomornya gabener")
            return
        
        file_rel_path = hasil[nomor - 1]
        await ctx.invoke(bot.get_command("play"), nama_file=file_rel_path)

    @bot.command()
    async def refresh(ctx):
        state.file_cache = music_cache.buat_music_cache()
        state.cache_timestamp = time.time()
        await ctx.send(f"cache nya lu update nih: {len(state.file_cache)} entries lu mbut")

    @bot.command()
    async def pause(ctx):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await ctx.send("mengheningkan cipta bentar")
        else:
            await ctx.send("tuli kah? gada musiknya")

    @bot.command()
    async def resume(ctx):
        async with player.kunci_lagu(ctx.guild.id):
            voice_client = ctx.voice_client
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await ctx.send("infokan penglanjutan musik")
            else:
                await ctx.send("tuli kah? gada musik yg berhenti")

    @bot.command()
    async def now(ctx):
        async with player.kunci_lagu(ctx.guild.id):
            guild_id = ctx.guild.id
            if guild_id in state.current_playing:
                current = state.current_playing[guild_id]

                if isinstance(current, dict):
                    await ctx.send(f"lu lagi dengerin: {current.get('title')}")
                else:
                    await ctx.send(f"lu lagi dengerin: {os.path.basename(current)}")
            else:
                await ctx.send("tuli kah? gada musiknya")
        
    @bot.command()
    async def next(ctx):
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if not voice_client or not voice_client.is_connected():
                state.current_playing.pop(guild_id, None)
                state.queue_asli.pop(guild_id, None)
                state.play_queue.pop(guild_id, None)
                await ctx.send("Botnya gada di dalem, pake !join")
                return
            if not voice_client.is_playing() and not voice_client.is_paused():
                await ctx.send("tuli kah? gada musiknya")
                return
        voice_client.stop()
        await ctx.send("skip dah ke lagu berikutnya")

    @bot.command()
    async def volume(ctx, level: int):
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if 0 <= level <= 100:
                state.tingkat_suara[guild_id] = level / 100
                await ctx.send(f"volume lu di atur di {level}")
            else:
                await ctx.send("atur volume sampe 0-100 dongok")

    @bot.command()
    async def repeat(ctx):
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            baru = not state.ulang_lagu.get(guild_id, False)
            state.ulang_lagu[guild_id] = baru
            await ctx.send(f"repeat nya lagi: {'nyala' if baru else 'mati'}")

