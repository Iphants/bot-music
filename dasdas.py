import discord
from discord.ext import commands 
from discord import FFmpegPCMAudio, PCMVolumeTransformer
import os
import difflib
import traceback
from functools import partial
from collections import deque
import time
import asyncio
import random
from random import shuffle as sf

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
backup_queue = {}
is_shuffle = {}
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
daftar_musik = r"E:\Music"
queues={}
current_playing = {}
file_cache = {}
cache_timestamp = 0
cache_durasi = 30
tingkat_suara = {}
ulang_lagu = {}
kunci_guild = {}
flag_shuffle = {}
queue_asli = {}
play_queue = {}

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
    
def kunci_lagu(guild_id):
    if guild_id not in kunci_guild:
        kunci_guild[guild_id] = asyncio.Lock()
    return kunci_guild[guild_id]

def cari_file_cocok(nama_file):
    try:
        semua_file_cache = dapetin_cache_file()
        nama_file_lower = nama_file.lower().strip()
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
    
def after_play(guild_id, voice_client, error):
    if error:
        print(f"error pas mainin (guild {guild_id}): {error}")
    try:
        if ulang_lagu.get(guild_id, False):
            if voice_client.is_playing():
                return
            lagu = current_playing.get(guild_id)
            if lagu:
                path = os.path.join(daftar_musik, lagu)
                source = FFmpegPCMAudio(source=path, executable="FFmpeg", options= "-vn -loglevel panic")
                volume = tingkat_suara.get(guild_id, 0.5)
                source = PCMVolumeTransformer (source, volume=volume)
                voice_client.play(source, after=partial(after_play, guild_id, voice_client))
            return
        if flag_shuffle.get(guild_id, False):
            shuffle_queue(guild_id)
        asyncio.run_coroutine_threadsafe(
            play_next(guild_id, voice_client),
            bot.loop
        )
    except Exception as e:
        print (f"after_play handler error {e}")
        current_playing.pop(guild_id, None)

def shuffle_queue(guild_id):
    if guild_id not in queues or not queues[guild_id]:
        return
    temp = list(queues[guild_id])
    sf(temp)
    queues[guild_id] = deque(temp)

def shuffle_internal(guild_id):
    q = list(play_queue[guild_id])
    if len (q) <= 1:
        return
    kepala = q[0]
    ekor = q[1:]
    random.shuffle(ekor)
    play_queue[guild_id] = deque([kepala]+ekor)

def ensure_deques(guild_id):
    if guild_id not in queue_asli:
        queue_asli[guild_id] = deque()
        if guild_id not in play_queue:
            play_queue[guild_id] = deque()

async def play_next(guild_id, voice_client):
    if not voice_client or not voice_client.is_connected():
        current_playing.pop(guild_id, None)
        queue_asli.pop(guild_id, None)
        play_queue.pop(guild_id, None)
        return
    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)
    if not play_queue.get(guild_id) or len(play_queue[guild_id]) == 0:
        current_playing.pop(guild_id, None)
        print (f"antrian kosong jir untuk guild {guild_id}")
        return
    while play_queue[guild_id]:
        file_rel_path = play_queue[guild_id].popleft()
        try:
            if file_rel_path in queue_asli.get(guild_id, []):
                queue_asli[guild_id].remove(file_rel_path)
        except ValueError:
            pass
        path_full = os.path.join(daftar_musik, file_rel_path)
        if not os.path.exists(path_full):
            print (f"file ilang, nooo:{path_full}")
            continue
        current_playing[guild_id] = file_rel_path
        try:
            src = FFmpegPCMAudio(source=path_full, executable="FFmpeg", options="-vn -loglevel panic")
            vol =tingkat_suara.get(guild_id, 0.5)
            source = PCMVolumeTransformer(src, volume=vol)
            voice_client.play(source, after=partial(after_play, guild_id, voice_client))
            return
        except Exception as e:
            print(f"Gagal ngeplay jir:{path_full}: {e}")
            current_playing.pop(guild_id, None)
            continue
    current_playing.pop(guild_id, None)
    print("gada lagu yang valid yang bisa di puter jir")            

@bot.event
async def on_ready():
    print (f"Bot {bot.user} on aktif dinyalakan")
    dapetin_cache_file()

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
        original = error.original
        embed.description = f"error internal: {error.original}"
        print(traceback.format_exc())
    else:
        embed.description = f"error gajelas: {error}"
    try:    
        await ctx.send(embed=embed)
    except Exception:
        print("gagal kirim embed error")

@bot.command()
async def help (ctx, command_name: str = None):
    data_tolong={
        "join": {
            "deskripsi": "bot masuk ke voice lu berada",
            "cara pake": "!join",
            "contoh": "!join"   
        },
        "play": {
            "deskripsi": "mainin lagu yang lu mau, asal file nya ada di pc gw",
            "cara pake": "!play <nama_lagu>",
            "contoh": "!play rabbit hole\n!play Shoujo rei"
        },
        "queue": {
            "deskripsi": "ngeliat antrian yang lagi ada",
            "cara pake": "!queue",
            "contoh": "!queue"
        },
        "now": {
            "deskripsi": "ngeliat lu lagi mainin lagu apa",
            "cara pake": "!now",
            "contoh": "!now"
        },
        "search": {
            "deskripsi": "nyari lagu lu ada apa kagak",
            "cara pake": "!search",
            "contoh": "!search rabbit hole\n!search shoujo rei"
        },
        "pause": {
            "deskripsi": "nge pause lagu yang lagi lu maiinin",
            "cara pake": "!pause",
            "contoh": "!pause"
        },
        "resume": {
            "deskripsi": "ngelanjutin lagu yang di pause",
            "cara pake": "!pause <saat_terputar_lagu>",
            "contoh": "!resume"
        }, 
        "shuffle":{
            "deskripsi": "ngacocok-ngocok antrian lu bukan peler ya",
            "cara pake": "!shuffle",
            "contoh": "!shuffle"
        },
        "next": {
            "deskripsi": "ngelanjutin musik kalau ada antriannya",
            "cara pake": "!next",
            "contoh": "!next"
        },
        "refresh": {
            "deskripsi": "nge refesh cache klo bot rada dongo",
            "cara pake": "!refresh",
            "contoh": "!refresh"
        },
        "volume": {
            "deskripsi": "ngatur volume botnya",
            "cara pake": "!volume <level_volume>",
            "contoh": "!volume 100"
        },
        "leave": {
            "deskripsi": "ngeluarin bot dari voice",
            "cara pake": "!leave",
            "contoh": "!leave"
        },
       #"remove": {
           # "deskripsi":"ngehapus lagu di antrian lu (ga berlaku untuk lagu yang lagi dimainin)",
          #  "cara pake":"!remove <angka_antrian> atau !remove <nama_lagu>",
           # "contoh":"!remove 1 atau !remove telepathy"
        #},
        "help": {
            "deskripsi": "nampilin ginian",
            "cara pake": "!help ato ga !help<command>",
            "contoh": "!help\n!help play"
        },
        "repeat": {
            "deskripsi": "ngulangin lagu yang lagi lu mainin",
            "cara pake": "!repeat",
            "contoh" : "!repeat"
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
            embed.add_field(name="deskripsi",value=data["deskripsi"], inline=False)
            embed.add_field(name="cara pake", value=f"'{data['cara pake']}", inline=False)
            embed.add_field(name="contoh", value=f"'{data['contoh']}", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Komand !{command_name} ga ada, ato ga blom gw tambahin")
    else:
        embed=discord.Embed(
            title="*pertolongan bot*",
            description="List komand yang gw masukin:",
            color=0x7289DA
        )
        basic_komand=""
        playback_komand=""
        queue_komand=""
        komand_lainnya=""
        for cmd, data in data_tolong.items():
            line = f"- '!{cmd}' - {data['deskripsi']}\n"
            if cmd in ["join", "leave", "help"]:
                basic_komand += line
            elif cmd in ["play", "search", "refresh", "repeat", "volume"]:
                playback_komand += line
            elif cmd in ["pause", "resume", "next", "now", #"remove",
                         "shuffle"]:
                queue_komand += line
        if basic_komand:
            embed.add_field(name="*basic komand*", value=basic_komand, inline=False)
        if playback_komand:
            embed.add_field(name="*playback komand*", value=playback_komand, inline=False)
        if queue_komand:
            embed.add_field(name="*queue komand*", value=queue_komand, inline=False)        
        if komand_lainnya:
            embed.add_field(name="*komand yang lain*", value=komand_lainnya, inline=False)
        embed.set_footer(text="pake !help <command> klo lu mau tw lebih lajut")
        await ctx.send(embed=embed)
    
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
    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)
        tampilan = queue_asli.get(guild_id, deque())
        if not tampilan and guild_id not in current_playing:
            return await ctx.send("kososng antriannya kek masa depan lu")
        now_current_playing = ""
        if guild_id in current_playing:
            now_current_playing = f"SABAR INI LAGI PLAY {os.path.basename(current_playing[guild_id])}\n\n"
        formatted = "\n".join([f"{i+1}. {os.path.basename(f)}" for i, f in enumerate(tampilan)])
        await ctx.send(f"{now_current_playing}nih antirannya\n{formatted if formatted else '(kosong)'}")

@bot.command()
async def play(ctx, *, nama_file: str):
    voice_client = ctx.voice_client
    if not voice_client: 
        await ctx.send("Botnya gada di dalem, pake !join")
        return
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)
    file_rel_path = cari_file_cocok(nama_file)
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
    is_playing_now = (voice_client.is_playing() or voice_client.is_paused() or guild_id in current_playing)
    if is_playing_now:
        queue_asli[guild_id].append(file_rel_path)
        play_queue[guild_id].append(file_rel_path)
        posisi = len(queue_asli[guild_id])
        await ctx.send(f"sabar, embut, nih masuk ke antrian posisi {posisi}: {os.path.basename(file_rel_path)}")
        return
    current_playing[guild_id] = file_rel_path
    ensure_deques(guild_id)
    try:
        current_playing[guild_id] = file_rel_path
        ff_source = FFmpegPCMAudio(source=file_path_full, executable="FFmpeg", options="-vn -loglevel panic")
        volume = tingkat_suara.get(guild_id, 0.5)
        source = PCMVolumeTransformer(ff_source, volume=volume)
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
    async with kunci_lagu(ctx.guild.id):
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await ctx.send("infokan penglanjutan musik")
        else:
            await ctx.send("tuli kah? gada musik yg berhenti")

@bot.command()
async def now(ctx):
    async with kunci_lagu(ctx.guild.id):
        guild_id = ctx.guild.id
        if guild_id in current_playing:
            await ctx.send (f"lu lagi dengerin: {os.path.basename(current_playing[guild_id])}")
        else:
            await ctx.send("tuli kah gada musiknya")

@bot.command()
async def next(ctx):
    voice_client = ctx.voice_client
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        if not voice_client or not voice_client.is_connected():
            await ctx.send("Botnya gada di dalem, pake !join")
            return
        if not voice_client.is_playing() and not voice_client.is_paused():
            await ctx.send("tuli kah? gada musiknya")
            return
        voice_client.stop()
        await ctx.send("skip dah ke lagu berikutnya")

@bot.command()
async def leave (ctx):
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        if ctx.voice_client:
            queue_asli.pop(guild_id, None)
            play_queue.pop(guild_id, None)
            current_playing.pop(guild_id, None)
            await ctx.voice_client.disconnect()
            await ctx.send("botnya gada di dalem, pake !join")

@bot.command()
async def volume (ctx, level: int):
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        if 0 <= level <= 100:
            tingkat_suara[guild_id] = level / 100
            await ctx.send(f"volume lu di atur di {level}")
        else:
            await ctx.send("atur volume sampe 0-100 dongok")

@bot.command()
async def clear(ctx):
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        if guild_id not in queues or not queues[guild_id]:
            return await ctx.send ("ngapain ongok gada antrian bjir")
        queues[guild_id].clear ()
        await ctx.send ("gw hapus nih, gusah nyesel")    

@bot.command()
async def repeat(ctx):
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        baru = not ulang_lagu.get(guild_id, False)
        ulang_lagu[guild_id] = baru
        await ctx.send(f"repeat nya lagi: {'nyala' if baru else 'mati'}")  

@bot.command()
async def shuffle(ctx):
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)
        if not queue_asli.get(guild_id) and guild_id not in current_playing:
            return await ctx.send("antrian kosong, mw ngocok apaan?")
        if is_shuffle .get(guild_id, False):
            play_queue[guild_id] = deque(queue_asli[guild_id])
            is_shuffle[guild_id] = False
            flag_shuffle[guild_id] = False
            return await ctx.send("shuffle nya mati, gw balikin ya urutannya")
        yg_dateng = list(queue_asli[guild_id])
        if not yg_dateng:
            return await ctx.send("isi antriannya dongok, yakali ngocok 1 lagu")
        random.shuffle(yg_dateng)
        play_queue[guild_id] = deque (yg_dateng)
        is_shuffle[guild_id] = True
        flag_shuffle[guild_id] = True
        return await ctx.send("gw kocok yaa antriannya, gausah nyesel klo muter yg aneh")

@bot.command()
async def remove(ctx, *, target):
    guild_id = ctx.guild.id
    async with kunci_lagu(guild_id):
        ensure_deques(guild_id)
        if not queue_asli.get(guild_id):
            return await ctx.send ("Antrian kosong kek masa depan lu")
        if target.isdigit():
            pos = int(target) - 1
            if pos < 0 or pos >= len(queue_asli[guild_id]):
                return await ctx.send("salah angka lu nya")
            removed = queue_asli[guild_id][pos]
            del queue_asli[guild_id][pos]
            try:
                play_queue[guild_id].remove(removed)
            except Exception:
                pass
            return await ctx.send(f"gw hapus ya: {os.path.basename(removed)}")
        target_ = target.lower().strip()
        exact_matches = []
        substring_matches = []
        for i, file_path in enumerate(list(queue_asli[guild_id])):
            base = os.path.basename(file_path)
            base_low = base.lower()
            name_no_ext = os.path.splitext(base_low)[0]
            if target_ == base_low or target_ == name_no_ext:
                exact_matches.append((i, file_path))
            elif target_ in base_low or target_ in name_no_ext:
                substring_matches.append((i, file_path))
        if len(exact_matches) == 1:
            idx, removed_path = exact_matches[0]
            del queue_asli[guild_id][idx]
            try:
                play_queue[guild_id].remove(removed_path)
            except Exception:
                pass
            return await ctx.send(f"gw hapus ya: {os.path.basename(removed_path)}")
        elif len(exact_matches) > 1:
            lines = [f"{j+1}. {os.path.basename(p)}" for j, (_, p) in enumerate(exact_matches)]
            return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))
        if len(substring_matches) == 1:
            idx, removed_path = substring_matches[0]
            del queue_asli[guild_id][idx]
            try:
                play_queue[guild_id].remove(removed_path)
            except Exception:
                pass
            return await ctx.send(f"gw hapus ya: {os.path.basename(removed_path)}")
        elif len(substring_matches) > 1:
            lines = [f"{j+1}. {os.path.basename(p)}" for j, (_, p) in enumerate(substring_matches)]
            return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))
        semua_nama = [os.path.splitext(os.path.basename(f))[0].lower() for f in queue_asli[guild_id]]
        kandidat = difflib.get_close_matches(target_, semua_nama, n=5, cutoff=0.3)
        if kandidat:
            saran_lines = []
            for k in kandidat:
                for f in queue_asli[guild_id]:
                    if os.path.splitext(os.path.basename(f))[0].lower() == k:
                        saran_lines.append(f"- {os.path.basename(f)}")
                        break
            saran = "\n".join(saran_lines)
            return await ctx.send(f"ga nemu '{target}', maksud lu yg ini?\n{saran}")
        return await ctx.send("ga ketemu antriannya, pmo mulu sih jadi lupa antriannya sendiri")
    
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return
    if before.channel and not after.channel:
        guild_id = before.channel.guild.id
        async with kunci_lagu(guild_id):
            queue_asli.pop(guild_id, None)
            play_queue.pop(guild_id, None)
            current_playing.pop(guild_id, None)

bot.run("bot_token")
