from __future__ import annotations
import difflib
import os
import random
import discord
from collections import deque
from discord.ext import commands
from .. import player
from .. import checks
from .. import state
from ..autoalir_store import save_queue
from .playback import nama_queue


# command yang ngurus antrian doang, dipasang dari main.py
def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def queue(ctx, page: int = 1):
        # nampilin queue asli yang keliatan user
        guild_id = ctx.guild.id
        per_page = 10

        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)

            daftar = list(state.play_queue.get(guild_id, []))
            current = state.current_playing.get(guild_id)

            if not current and not daftar:
                return await ctx.send("Antrean kosong")
            
            total = len(daftar)
            max_page = max(1, (total - 1) // per_page + 1)
            page = max(1, min(page, max_page))
            start = (page - 1) * per_page
            end = start + per_page
            potongan = daftar[start:end]
            embed = discord.Embed(title="Antrean musik", color=0x41639b,)

            if isinstance(current, dict):
                now_txt = current.get("title", "Unknown YouTube")
                uploader = current.get("uploader")
                if uploader:
                    now_txt += f" — {uploader}"
            elif current:
                now_txt = nama_queue (current)
            else:
                now_txt = "Tak da lagu yang diputar"

            embed.description = f"**Lagi diputer:**\n {now_txt}"
            lines = []
            for idx, item in enumerate(potongan, start=start+1):
                lines.append(f"{idx}. {nama_queue(item)}")

            embed.add_field(name="Berikutnya", value="\n".join(lines) if lines else "(kosong)", inline=False)

            footer = f"Halaman {page}/{max_page} • Total {total} lagu"
            if state.is_shuffle.get(guild_id, False):
                footer += " • Shuffle nyala"
            embed.set_footer(text=footer)
            await ctx.send (embed=embed)

    @bot.command()
    async def shuffle(ctx):
        # acak queue play tanpa ngerusak urutan queue asli
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            if not state.queue_asli.get(guild_id) and guild_id not in state.current_playing:
                return await ctx.send("antrian kosong, mw ngocok apaan?")
            if state.is_shuffle.get(guild_id, False):
                state.play_queue[guild_id] = deque(state.queue_asli[guild_id])
                state.is_shuffle[guild_id] = False
                state.flag_shuffle[guild_id] = False
                save_queue(guild_id)
                return await ctx.send("shuffle nya mati, gw balikin ya urutannya")
            
            yg_dateng = list(state.queue_asli[guild_id])
            if not yg_dateng:
                return await ctx.send("isi antriannya dongok, yakali ngocok 1 lagu")
            random.shuffle(yg_dateng)
            state.play_queue[guild_id] = deque(yg_dateng)
            state.is_shuffle[guild_id] = True
            state.flag_shuffle[guild_id] = True
            save_queue(guild_id)
            return await ctx.send("gw kocok yaa antriannya, gausah nyesel klo muter yg aneh")

    @bot.command()
    async def remove(ctx, *, target):
        # hapus item queue, bisa by angka atau nama
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)

            if not state.play_queue.get(guild_id):
                return await ctx.send("Antrian kosong kek masa depan lu")
            
            # nama user-facing buat pesan remove/saran
            def item_name(item):
                return nama_queue(item)
            
            # key pencarian remove, gabung nama file/stem/display title
            def item_key(item):
                if isinstance(item, dict):
                    title = item.get("title", "")
                    return title.lower().strip()
                
                base = os.path.basename(item).lower().strip()
                stem = os.path.splitext(base)[0]
                dplay = nama_queue(item).lower().strip()
                return f"{base} {stem} {dplay}"
            
            # hapus dari play_queue dan queue_asli biar urutan tampilan tetap sinkron
            def hapus_playque(pos):
                daftar = list(state.play_queue[guild_id])
                removed = daftar.pop(pos)
                state.play_queue[guild_id] = deque(daftar)

                try:
                    state.queue_asli[guild_id].remove(removed)
                except ValueError:
                    pass
                return removed

            if target.isdigit():
                pos = int(target) - 1
                if pos < 0 or pos >= len(state.play_queue[guild_id]):
                    return await ctx.send("salah angka lu nya")

                removed = hapus_playque(pos)
                save_queue(guild_id)
                return await ctx.send(f"gw hapus ya: {item_name(removed)}")

            target_ = target.lower().strip()
            exact_matches = []
            substring_matches = []
            daftar_mcl = list(state.play_queue[guild_id])

            for i, item in enumerate(daftar_mcl):
                key = item_key(item)
                dspy = item_name(item).lower().strip()

                if target_ == dspy or target_ == key:
                    exact_matches.append((i, item))
                elif target_ in key:
                    substring_matches.append((i, item))

            if len(exact_matches) == 1:
                idx, removed_item = exact_matches[0]
                removed = hapus_playque(idx)
                save_queue(guild_id)
                return await ctx.send(f"ge hapus ya: {item_name(removed)}")
            
            if len(exact_matches) > 1:
                lines = [f"{i+1}. {item_name(item)}" for i, item in enumerate(exact_matches)]
                return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))
            
            if len(substring_matches) == 1:
                idx, removed_item = substring_matches[0]
                removed = hapus_playque(idx)
                save_queue(guild_id)
                return await ctx.send(f"gw hapus ya: {item_name(removed)}")

            if len(substring_matches) > 1:
                lines = [f"{i+1}. {item_name(item)}" for i, item in substring_matches]
                return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))

            semua_nama = [item_key(f).strip()for f in daftar_mcl]
            kandidat = difflib.get_close_matches(target_, semua_nama, n=5, cutoff=0.3)

            if kandidat:
                # cari saran manual, pendek aja jadi gapapa muter dua loop
                saran_lines = []
                for k in kandidat:
                    for i, item in enumerate(daftar_mcl):
                        if item_key(item).strip() == k:
                            saran_lines.append(f"{i+1} {item_name(item)}")
                            break
                        
                saran = "\n".join(saran_lines)
                return await ctx.send(f"ga nemu '{target}', maksud lu yg ini?\n{saran}")
            return await ctx.send("ga ketemu antriannya, pmo mulu sih jadi lupa antriannya sendiri")

    @bot.command()
    @checks.is_dj_or_admin()
    async def clear(ctx):
        # ngosongin dua queue sekalian; aksesnya dibatasi DJ/admin
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            if not state.queue_asli[guild_id] and not state.play_queue[guild_id]:
                return await ctx.send("ngapain ongok gada antrian bjir")
            state.queue_asli[guild_id].clear()
            state.play_queue[guild_id].clear()
            save_queue(guild_id)
            await ctx.send("gw hapus nih, gusah nyesel")
