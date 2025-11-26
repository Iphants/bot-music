import discord
from discord.ext import commands 
from discord import FFmpegPCMAudio, PCMVolumeTransformer
import os
import difflib
import traceback
from functools import partial
from collections import deque
import time

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
daftar_musik = r"E:\Music"
queues={}
current_playing = {}
file_cache = {}
cache_timestamp = 0
cache_durasi = 30

def buat_music_cache():
    music_files = {}
    ekstensi_valid = ('.mp3', '.wav', '.flac', '.m4a')
    try:
        for root, _, files in os.walk(daftar_musik):
            for file in files:
                if not file.lower().endswith(ekstensi_valid):
                        continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, daftar_musik)
                katkunc_nama = file.lower()
                katkunc_rel = rel_path.replace(os.sep, '/').lower()
                music_files.setdefault(katkunc_nama, []).append(rel_path)
                music_files.setdefault(katkunc_rel, []).append(rel_path)
        print(f"isi cache:{len (music_files)} entries")
        return music_files
    except Exception as e:
        print(f"error ngebangun cache {e}")
        return{}    
    
def dapetin_cache_file():
    global file_cache, cache_timestamp
    sekarang = time.time()
    if not file_cache or (sekarang - cache_timestamp > cache_durasi):
        file_cache = buat_music_cache()
        cache_timestamp = sekarang
    return file_cache

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
    
def cari__file_cocok(nama_file):
    try:
        semua_file_cache = dapetin_cache_file()
        nama_file_lower = nama_file.lower()
        if nama_file_lower in semua_file_cache:
            return semua_file_cache[nama_file_lower][0]
        qnorm = nama_file_lower.replace("\\", "/")
        if qnorm in semua_file_cache:
            return semua_file_cache[qnorm][0]
        if not any(nama_file_lower.endswith(ext)for ext in ('.mp3', '.wav', '.flac', '.m4a')):
            for ext in ('.flac', '.mp3', '.wav', '.m4a'):
                nama_file_ext = nama_file_lower + ext
                if nama_file_ext in semua_file_cache:
                    return semua_file_cache[nama_file_ext][0]
        hasil_fuzzy = cari_lagu(nama_file)
        if hasil_fuzzy:
            return hasil_fuzzy[0]
        return None
    except Exception as e:
        print(f"Error nyari file nya jir: {e}")
        return None
    
def after_play(guild_id, voice_client, error):
    if error:
        print(f"error pas mainin (guild {guild_id}): {error}")
    try:
        if voice_client and getattr(voice_client, "is_connected", lambda: False)():
            play_next(guild_id, voice_client)
        else:
            current_playing.pop(guild_id, None)
            queues.pop(guild_id, None)
    except Exception as e:
        print (f"after_play handler error {e}")
        current_playing.pop(guild_id, None)

def play_next(guild_id, voice_client):
    try:
        if guild_id in queues and queues[guild_id]:
            lagu_berikutnya = queues[guild_id].popleft()
            current_playing[guild_id] = lagu_berikutnya
            path_penuh = os.path.join(daftar_musik, lagu_berikutnya)
            if not os.path.exists(path_penuh):
                print(f"file not found saat play_next: {path_penuh}")
                play_next (guild_id, voice_client)
                return
            ff_source = FFmpegPCMAudio(source=path_penuh, executable="ffmpeg", options="-vn -loglevel panic")
            source = PCMVolumeTransformer(ff_source, volume=0.5)
            voice_client.play(source, after=partial(after_play, guild_id, voice_client))
        else:
            current_playing.pop(guild_id, None)
            if guild_id in queues and not current_playing:
                queues[guild_id] = deque()
            print (f"antrian abis untuk guild {guild_id}")
    except Exception as e:
        print (f"Error mainin lagu selanjutnya ajah: {e}")
        current_playing.pop(guild_id, None)

@bot.event
async def on_ready():
    print (f"Bot {bot.user} on aktif dinyalakan")
    dapetin_cache_file()

@bot.event
async def help (ctx, command_name: str = None):
    data_tolong= {
        "join": {
            "deskripis:" "bot masuk ke voice lu berada"
            "cara pake:" "!join"
            "contoh:" "!join"   
        },
        "play": {
            "deskripsi:" "mainin lagu yang lu mau, asal file nya ada di pc gw"
            "cara pake:" "!play <nama_lagu>"
            "contoh:" "!play rabbit hole\n!play Shoujo rei"
        },
        "queue": {
            "deskripsi:" "ngeliat antrian yang lagi ada"
            "cara pake:" "!queue"
            "contoh:" "!queue"
        },
        "now": {
            "deskripsi:" "ngeliat lu lagi mainin lagu apa"
            "cara pake:" "!now"
            "contoh:" "!now"
        },
        "search": {
            "deskripsi:" "nyari lagu lu ada apa kagak"
            "cara pake:" "!search"
            "contoh:" "!search rabbit hole\n!search shoujo rei"
        },
        "pause": {
            "deskripsi:" "nge pause lagu yang lagi lu maiinin"
            "cara pake:" "!pause"
            "contoh:" "!pause"
        },
        "resume": {
            "deskripsi:" "ngelanjutin lagu yang di pausse"
            "cara pake:" "!pause <saat_terputar_lagu>"
            "contoh:" "!resume"
        },
        "next": {
            "deskripsi:" "ngelanjutin musik kalau ada antriannya"
            "cara pake:" "!next"
            "contoh:" "!next"
        },
        "refresh": {
            "deskripsi:" "nge refesh cache klo bot rada dongo"
            "cara pake:" "!refresh"
            "contoh:" "!refresh"
        },
        "volume": {
            "deskripsi:" "ngatur volume botnya"
            "cara pake:" "!volume <level_volume>"
            "contoh:" "!volume 100"
        },
        "leave": {
            "deskripsi:" "ngeluarin bot dari voice"
            "cara pake:" "!leave"
            "contoh:" "!leave"
        },
        "help": {
            "deskripsi:" "nampilin ginian"
            "cara pake:" "!help ato ga !help<command>"
            "contoh:" "!help\n!help play"
        }
    }
    if command_name:
        command_name = command_name.lower()
        if command_name in data_tolong:
            data = data_tolong[command_name]
            embed = discord.Embed(
                title=f"Komand: !{command_name}",
                color=0x00ff00
            )
            embed.add_feld(name="deskripsi",value=data["deskripsi"], inline=False)
            embed.add_feld(name="cara pake", value=f"'{data['cara pake']}", inline=False)
            embed.add_feld(name="contoh", value=f"'{data['contoh']}", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Komand !{command_name} ga ada, ato ga blom gw tambahin")
    else:
        embed=discord.Embed(
            judul="*pertolongan bot*",
            deskripsi="List komand yang gw masukin:",
            color=0x7289FDA
        )
        basic_komand=""
        playback_komand=""
        queue_komand=""
        komand_lainnya=""
        for cmd, data in data_tolong.items():
            line = f"- '!{cmd}' - {data['deskripsi']}\n"
            if cmd in ["join", "leave", "help"]:
                basic_komand += line
            elif cmd in ["play", "search", "refresh"]:
                basic_komand += line
            elif cmd in ["pause", "resume", "next", "now"]:
                kontrol_komand += line
        if basic_komand:
            embed.add_feld(name="*basic komand*", value=basic_komand, inline=False)
        if playback_komand:
            embed.add_feld(name="*playback komand*", value=playback_komand, inline=False)
        if queue_komand:
            embed.add_feld(name="*queue komand*", value=queue_komand, inline=False)        
        if komand_lainnya:
            embed.add_feld(name="*komanf yang lain*", value=komand_lainnya, inline=False)
        embed.sed_footer(text="pake !help <command> klo lu mau tw lebih lajut")
        await ctx.send(embed=embed)
    
@bot.event
async def on_command_error(ctx, error):
    embed = discord.Embed(title="Error", color=discord.Color.red())
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        embed.description = f"Argumen '{error.param.name}' wajib diisi"
    elif isinstance(error, commands.CommandOnCooldown):
        embed.description = f"Sabar jembut, coba lagi pas '{error.retry_after:.2f} detik."
    elif isinstance(error, commands.MissingPermissions):
        embed.description = f"Permission lu kurang: '{','.join(error.missing_permissions)}"
    elif isinstance(error, commands.CommandInvokeError):
        embed.description = f"error internal: {error.original}"
        print(traceback.format_exc())
    else:
        embed.description = f"error gajelas: {error}"
    try:    
        await ctx.send(embed=embed)
    except Exception:
        print("gagal kirim embed error")

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send("Bot masuk ke voice")
    else:
        await ctx.send("Masuk voice dlu baru bisa")

@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    if guild_id not in queues or not queues[guild_id]:
        await ctx.send ("kosong antriannya kek masa depan lu.")
        return
    now_current_playing = ""
    if guild_id in current_playing:
        now_current_playing = f"SABAR INI LAGI PLAY {os.path.basename(current_playing[guild_id])}\n\n"
    formatted = "\n".join([f"{i+1}. {os.path.basename(f)}" for i, f in enumerate(queues[guild_id])])
    await ctx.send(f"{now_current_playing} nih antriannya\n{formatted}")

@bot.command()
async def play(ctx, *, nama_file: str):
    voice_client = ctx.voice_client
    if not voice_client: 
        await ctx.send("Botnya gada di dalem, pake !join")
        return
    guild_id = ctx.guild.id
    queues.setdefault(guild_id, [])
    if guild_id not in queues or not isinstance(queues[guild_id], deque):
        queues[guild_id] = deque()
    file_rel_path = cari__file_cocok(nama_file)
    if not file_rel_path:
        hasil_saran = cari_lagu(nama_file)
        if hasil_saran:
            saran = "\n".join([f"-{os.path.basename(f)}"for f in hasil_saran[:20]])
            await ctx.send(f"Blom gw tambahin jir {nama_file}, yang ini kah?\n{saran}")
            return
        else:
            await ctx.send("Blom gw tambahin jir musiknya")
            return
    file_path_full = os.path.join(daftar_musik, file_rel_path)
    if not os.path.exists(file_path_full):
            await ctx.send("Musiknya corrupt atau hilang jir")
            return       
    should_queue = (
        voice_client.is_playing() or 
        voice_client.is_paused() or
        guild_id in current_playing or  
        (guild_id in queues and len(queues[guild_id]) > 0)
    )
    if should_queue:
        position = len(queues[guild_id]) + 1
        queues[guild_id].append(file_rel_path)
        nama_file_muncul = os.path.basename(file_rel_path)
        await ctx.send(f"sabar embut, nih masuk ke antrian posisi {position}: {nama_file_muncul}")
        return
    try:
        current_playing[guild_id] = file_rel_path
        ff_source = FFmpegPCMAudio(source=file_path_full, executable="ffmpeg", options="-vn -loglevel panic")
        source = PCMVolumeTransformer(ff_source, volume=0.5)
        voice_client.play(source, after=partial(after_play, guild_id, voice_client))
        await ctx.send (f"Lagi jalanin ini le: {os.path.basename(file_rel_path)}")
    except Exception as e:
        current_playing.pop(guild_id, None)
        await ctx.send (f"error anjay {e}")
        print(traceback.format_exc())

@bot.command()
async def search(ctx, *, query: str):
    hasil = cari_lagu(query)
    if not hasil:
        await ctx.send ("Blom gw tambahin jir musiknya")
        return
    format_baris = []
    for file_path in hasil [:20]:
        if "\\" in file_path or "/" in file_path:
            folder = os.path.dirname(file_path)
            nama_file = os.path.basename(file_path)
            format_baris.append(f"-{nama_file}(di {folder})")
        else:
            format_baris.append(f"-{file_path}")
    formatted = "\n".join(format_baris)
    await ctx.send(f"nih ya embut '{query}':\n{formatted}")

@bot.command()
async def refresh (ctx):
    global file_cache, cache_timestamp
    file_cache = buat_music_cache()
    cache_timestamp = time.time()
    await ctx.send(f"cache nya lu update nih: {len(file_cache)} entries lu mbut")

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
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("infokan penglanjutan musik")
    else:
        await ctx.send("tuli kah? gada musik yg berhenti")

@bot.command()
async def now(ctx):
    guild_id = ctx.guild.id
    if guild_id in current_playing:
        await ctx.send (f"lu lagi dengerin: {os.path.basename(current_playing[guild_id])}")
    else:
        await ctx.send("tuli kah gada musiknya")

@bot.command()
async def next(ctx):
    voice_client = ctx.voice_client
    guild_id = ctx.guild.id
    if not voice_client or not voice_client.is_connected():
        await ctx.send("Botnya gada di dalem, pake !join")
        return
    if not voice_client.is_playing() and not voice_client.is_paused():
        await ctx.send("tuli kah? gada musiknya")
        return
    if guild_id in queues and queues[guild_id]:
        voice_client.stop()
        await ctx.send("skip dah lagu berikutnya")
    else:
        voice_client.stop()
        if guild_id in current_playing:
            del current_playing[guild_id]
            await ctx.send("Gada antrian, isi dlu oon, sekalian berhenti bentar lagunya")

@bot.command()
async def leave (ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in queues:
            del queues[guild_id]
        if guild_id in current_playing:
            del current_playing[guild_id]
        await ctx.voice_client.disconnect()
        await ctx.send("bot kabur dlu le.")
    else:
        await ctx.send("Botnya gada di dalem")

@bot.command()
async def volume (ctx, level: int):
    if 0 <= level <= 100:
        await ctx.send(f"volume lu di atur di {level}")
    else:
        await ctx.send("atur volume sampe 0-100 dongok")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        guild_id = before.channel.guild.id
        if guild_id in queues:
            del queues[guild_id]
        if guild_id in current_playing:
            del current_playing[guild_id]
bot.run("isi_tokenmu")
