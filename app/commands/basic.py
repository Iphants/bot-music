from __future__ import annotations
from discord.ext import commands
from .. import player, state
import discord
import asyncio

# ===== COMMAND BASIC =====
def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def help(ctx, command_name: str = None):
        # ===== HELP DATA =====
        data_tolong = {
            "join": {
                "deskripsi": "bot masuk ke voice lu berada",
                "cara pake": "!join",
                "contoh": "!join",
            },
            "play": {
                "deskripsi": "mainin lagu yang lu mau, asal file nya ada di pc gw",
                "cara pake": "!play <nama_lagu>",
                "contoh": "!play rabbit hole\n!play Shoujo rei",
            },
            "queue": {
                "deskripsi": "ngeliat antrian yang lagi ada",
                "cara pake": "!queue",
                "contoh": "!queue",
            },
            "now": {
                "deskripsi": "ngeliat lu lagi mainin lagu apa",
                "cara pake": "!now",
                "contoh": "!now",
            },
            "search": {
                "deskripsi": "nyari lagu lu ada apa kagak",
                "cara pake": "!search",
                "contoh": "!search rabbit hole\n!search shoujo rei",
            },
            "pause": {
                "deskripsi": "nge pause lagu yang lagi lu maiinin",
                "cara pake": "!pause",
                "contoh": "!pause",
            },
            "resume": {
                "deskripsi": "ngelanjutin lagu yang di pause",
                "cara pake": "!pause <saat_terputar_lagu>",
                "contoh": "!resume",
            },
            "shuffle": {
                "deskripsi": "ngacocok-ngocok antrian lu bukan peler ya",
                "cara pake": "!shuffle",
                "contoh": "!shuffle",
            },
            "next": {
                "deskripsi": "ngelanjutin musik kalau ada antriannya",
                "cara pake": "!next",
                "contoh": "!next",
            },
            "refresh": {
                "deskripsi": "nge refesh cache klo bot rada dongo",
                "cara pake": "!refresh",
                "contoh": "!refresh",
            },
            "volume": {
                "deskripsi": "ngatur volume botnya",
                "cara pake": "!volume <level_volume>",
                "contoh": "!volume 100",
            },
            "leave": {
                "deskripsi": "ngeluarin bot dari voice",
                "cara pake": "!leave",
                "contoh": "!leave",
            },
            "remove": {
                "deskripsi": "ngehapus lagu di antrian lu (ga berlaku untuk lagu yang lagi dimainin)",
                "cara pake": "!remove <angka_antrian> atau !remove <nama_lagu>",
                "contoh": "!remove 1 atau !remove telepathy",
            },
            "help": {
                "deskripsi": "nampilin ginian",
                "cara pake": "!help ato ga !help<command>",
                "contoh": "!help\n!help play",
            },
            "repeat": {
                "deskripsi": "ngulangin lagu yang lagi lu mainin",
                "cara pake": "!repeat",
                "contoh": "!repeat",
            },
            "yt": {
                "deskripsi": "nyari dan muter lagu langsung dari YouTube",
                "cara pake": "!yt <judul_lagu>",
                "contoh": "!yt yoasobi tabun\n!yt alan walker faded",
            },
            "autoalir": {
                "deskripsi": "kalau antrian kosong, bot nyari lagu lokal yang masih satu rasa",
                "cara pake": "!autoalir <on/off>",
                "contoh": "!autoalir on\n!autoalir off",
            },
        }

        if command_name:
            command_name = command_name.lower()
            if command_name in data_tolong:
                data = data_tolong[command_name]
                embed = discord.Embed(title=f"Komand: !{command_name}", color=0xFFA500)
                embed.add_field(name="deskripsi", value=data["deskripsi"], inline=False)
                embed.add_field(name="cara pake", value=f"'{data['cara pake']}", inline=False)
                embed.add_field(name="contoh", value=f"'{data['contoh']}", inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Komand !{command_name} ga ada, ato ga blom gw tambahin")
        else:
            embed = discord.Embed(
                title="*pertolongan bot*",
                description="List komand yang gw masukin:",
                color=0xFFA500,
            )
            basic_komand = ""
            playback_komand = ""
            queue_komand = ""
            komand_lainnya = ""
            for cmd, data in data_tolong.items():
                line = f"- '!{cmd}' - {data['deskripsi']}\n"
                if cmd in ["join", "leave", "help"]:
                    basic_komand += line
                elif cmd in ["play", "search", "refresh", "repeat", "volume", "yt"]:
                    playback_komand += line
                elif cmd in ["pause", "resume", "next", "now", "remove", "shuffle", "autoalir"]:
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
    async def autoalir(ctx, mode: str = None):
        # ===== AUTOALIR MODE =====
        guild_id = ctx.guild.id

        if mode is None:
            status = "nyala" if state.mode_autoalir.get(guild_id, False) else "mati"
            await ctx.send(f"autoalir sekarang: {status}")
            return

        mode = mode.lower().strip()

        if mode in ("on", "nyala", "hidup"):
            state.mode_autoalir[guild_id] = True
            await ctx.send("autoalir: nyala")
            return

        if mode in ("off", "mati", "stop"):
            state.mode_autoalir[guild_id] = False
            await ctx.send("autoalir: mati")
            return

        await ctx.send("pake: !autoalir on / off")

    @bot.command()
    async def join(ctx):
        # ===== JOIN VOICE =====
        if not ctx.author.voice:
            await ctx.send("Masuk voice dulu")
            return
      
        guild_id = ctx.guild.id

        async with player.kunci_lagu(guild_id):
            print(f"[JOIN] dipanggil sama {ctx.author} guild = {guild_id}")
            channel = ctx.author.voice.channel
            vc = ctx.guild.voice_client

            if vc:
                if vc.channel != channel:
                    print("[JOIN] pindah channel")
                    await vc.move_to(channel)
                else:
                    print("[JOIN] dh di channel yg sama")
                    player.cancel_idle_leave(guild_id)
                    await ctx.send("udah ada di dalem voice ini")
                return
            else:
                print("[JOIN] connect baru")
                vc = await channel.connect()

            for _ in range(10):
                if vc and vc.is_connected() and vc.channel:
                    break
                await asyncio.sleep(0.2)
            if not vc or not vc.is_connected() or not vc.channel:
                await ctx.send("gagal connect ke voice (timeout)")
                return

            await asyncio.sleep(0.5)

            player.cancel_idle_leave(ctx.guild.id)
            print(f"[JOIN] ready:", vc and vc.is_connected(), "channel:", vc.channel if vc else None)
            await ctx.send("Bot masuk ke voice")

    @bot.command()
    async def leave(ctx):
        # ===== LEAVE VOICE =====
        guild_id = ctx.guild.id

        async with player.kunci_lagu(guild_id):
            vc = ctx.guild.voice_client
            if not vc or not vc.is_connected():
                await ctx.send("botnya gada di voice")
                return
            
            player.cancel_idle_leave(guild_id)
            state.queue_asli.pop(guild_id, None)
            state.play_queue.pop(guild_id, None)
            state.current_playing.pop(guild_id, None)
            await vc.disconnect(force=True)
            await ctx.send("Bot keluar dari voice")
