from __future__ import annotations
from discord.ext import commands
from .. import player, state
from ..autoalir_store import save_queue
import discord
import asyncio


def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def help(ctx, command_name: str = None):
        data_tolong = {
            "join": {
                "deskripsi": "bot masuk ke voice lu berada",
                "cara pake": "!join",
                "contoh": "!join",
            },
            "play": {
                "deskripsi": "muter lagu lokal dari folder musik",
                "cara pake": "!play <nama_lagu>",
                "contoh": "!play rabbit hole\n!play Shoujo rei",
            },
            "yt": {
                "deskripsi": "nyari dan muter lagu langsung dari YouTube",
                "cara pake": "!yt <judul_lagu>",
                "contoh": "!yt yoasobi tabun\n!yt alan walker faded",
            },
            "thumbnail": {
                "deskripsi": "ngirim cover lagu yang lagi diputer atau lagu lokal tertentu",
                "cara pake": "!thumbnail [raw] [nama_lagu]",
                "contoh": "!thumbnail\n!thumbnail raw\n!thumbnail rabbit hole",
            },
            "search": {
                "deskripsi": "nyari lagu lokal dari cache musik",
                "cara pake": "!search <query>",
                "contoh": "!search rabbit hole\n!search shoujo rei",
            },
            "pick": {
                "deskripsi": "milih hasil search berdasarkan nomor",
                "cara pake": "!pick <nomor>",
                "contoh": "!pick 1",
            },
            "refresh": {
                "deskripsi": "bangun ulang cache lagu dan metadata buat DJ/admin",
                "cara pake": "!refresh",
                "contoh": "!refresh",
            },
            "queue": {
                "deskripsi": "ngeliat antrian yang lagi ada",
                "cara pake": "!queue [halaman]",
                "contoh": "!queue\n!queue 2",
            },
            "now": {
                "deskripsi": "ngeliat lu lagi mainin lagu apa",
                "cara pake": "!now",
                "contoh": "!now",
            },
            "pause": {
                "deskripsi": "nge pause lagu yang lagi lu maiinin",
                "cara pake": "!pause",
                "contoh": "!pause",
            },
            "resume": {
                "deskripsi": "ngelanjutin lagu yang di pause",
                "cara pake": "!resume",
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
            "volume": {
                "deskripsi": "ngatur volume botnya buat DJ/admin",
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
            "clear": {
                "deskripsi": "ngosongin semua antrian buat DJ/admin",
                "cara pake": "!clear",
                "contoh": "!clear",
            },
            "help": {
                "deskripsi": "nampilin ginian",
                "cara pake": "!help atau !help <command>",
                "contoh": "!help\n!help play",
            },
            "repeat": {
                "deskripsi": "ngulangin lagu yang lagi lu mainin",
                "cara pake": "!repeat",
                "contoh": "!repeat",
            },
            "lyrics": {
                "deskripsi": "nampilin potongan lirik lagu yang lagi diputer",
                "cara pake": "!lyrics",
                "contoh": "!lyrics",
            },
            "lirik": {
                "deskripsi": "nampilin lirik atau nyalain/matiin live lyrics",
                "cara pake": "!lirik [live/on/off]",
                "contoh": "!lirik\n!lirik live\n!lirik off",
            },
            "autoalir": {
                "deskripsi": "kalau antrian kosong, bot nyari lagu lokal yang masih satu rasa",
                "cara pake": "!autoalir <on/off>",
                "contoh": "!autoalir on\n!autoalir off",
            },
            "library": {
                "deskripsi": "mencari folder musik manual (klik-klik folder/lagu)",
                "cara pake": "!library [halaman]",
                "contoh": "!library\n!library 2",
            },
            "open": {
                "deskripsi": "buka folder atau puter lagu dari nomor yang tampil di library",
                "cara pake": "!open <nomor>",
                "contoh": "!open 3",
            },
            "back": {
                "deskripsi": "balik ke folder sebelumnya di library",
                "cara pake": "!back",
                "contoh": "!back",
            },
        }

        if command_name:
            command_name = command_name.lower().strip().lstrip("!")
            if command_name in data_tolong:
                data = data_tolong[command_name]
                embed = discord.Embed(title=f"Komand: !{command_name}", color=0xFFA500)
                embed.add_field(name="deskripsi", value=data["deskripsi"], inline=False)
                embed.add_field(
                    name="cara pake", value=f"`{data['cara pake']}`", inline=False
                )
                embed.add_field(
                    name="contoh", value=f"`{data['contoh']}`", inline=False
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(
                    f"Komand !{command_name} ga ada, ato ga blom gw tambahin"
                )
        else:
            embed = discord.Embed(
                title="*pertolongan bot*",
                description="List komand yang gw masukin:",
                color=0xFFA500,
            )
            basic_komand = ""
            playback_komand = ""
            queue_komand = ""
            lirik_komand = ""
            library_komand = ""
            komand_lainnya = ""
            for cmd, data in data_tolong.items():
                line = f"- `!{cmd}` - {data['deskripsi']}\n"
                if cmd in ["join", "leave", "help", "autoalir"]:
                    basic_komand += line
                elif cmd in [
                    "play",
                    "yt",
                    "thumbnail",
                    "search",
                    "pick",
                    "refresh",
                    "repeat",
                    "volume",
                ]:
                    playback_komand += line
                elif cmd in [
                    "queue",
                    "pause",
                    "resume",
                    "next",
                    "now",
                    "remove",
                    "shuffle",
                    "clear",
                ]:
                    queue_komand += line
                elif cmd in ["lyrics", "lirik"]:
                    lirik_komand += line
                elif cmd in ["library", "open", "back"]:
                    library_komand += line
                else:
                    komand_lainnya += line
            if basic_komand:
                embed.add_field(name="*basic komand*", value=basic_komand, inline=False)
            if playback_komand:
                embed.add_field(
                    name="*playback komand*", value=playback_komand, inline=False
                )
            if queue_komand:
                embed.add_field(name="*queue komand*", value=queue_komand, inline=False)
            if lirik_komand:
                embed.add_field(name="*lirik komand*", value=lirik_komand, inline=False)
            if library_komand:
                embed.add_field(
                    name="*library komand*", value=library_komand, inline=False
                )
            if komand_lainnya:
                embed.add_field(
                    name="*komand yang lain*", value=komand_lainnya, inline=False
                )
            embed.set_footer(text="pake !help <command> klo lu mau tw lebih lajut")
            await ctx.send(embed=embed)

    @bot.command()
    async def autoalir(ctx, mode: str = None):
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
            print(
                "[JOIN] ready:",
                vc and vc.is_connected(),
                "channel:",
                vc.channel if vc else None,
            )
            await ctx.send("Bot masuk ke voice")

        if (
            vc
            and vc.is_connected()
            and state.play_queue.get(guild_id)
            and not vc.is_playing()
            and not vc.is_paused()
            and guild_id not in state.current_playing
        ):
            await ctx.send("nemu antrean kesimpen, lanjut dari situ yak")
            asyncio.create_task(player.play_next(guild_id, vc))

    @bot.command()
    async def leave(ctx):
        guild_id = ctx.guild.id

        async with player.kunci_lagu(guild_id):
            vc = ctx.guild.voice_client
            if not vc or not vc.is_connected():
                await ctx.send("botnya gada di voice")
                return
            player.cancel_idle_leave(guild_id)
            save_queue(guild_id)
            state.queue_asli.pop(guild_id, None)
            state.play_queue.pop(guild_id, None)
            state.current_playing.pop(guild_id, None)
            await vc.disconnect(force=True)
            await ctx.send("Bot keluar dari voice")
