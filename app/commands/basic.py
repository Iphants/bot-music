from __future__ import annotations
from discord.ext import commands
import discord

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
                elif cmd in ["pause", "resume", "next", "now", "remove", "shuffle"]:
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
        if not ctx.author.voice:
            await ctx.send("Masuk voice dlu baru bisa")
            return
        channel = ctx.author.voice.channel

        if ctx.voice_client:
            if ctx.voice_client.channel == channel:
                await ctx.send("udah ada di dalem voice ini")
                return 
            await ctx.voice_client.move_to(channel)
            return
        await channel.connect()
        await ctx.send("Bot masuk ke voice")
    

    @bot.command()
    async def leave(ctx):
        guild_id = ctx.guild.id
        from .. import player, state

        async with player.kunci_lagu(guild_id):
            if ctx.voice_client:
                player.cancel_idle_leave(guild_id)
                state.queue_asli.pop(guild_id, None)
                state.play_queue.pop(guild_id, None)
                state.current_playing.pop(guild_id, None)
                await ctx.voice_client.disconnect()
                await ctx.send("botnya gada di dalem, pake !join")

