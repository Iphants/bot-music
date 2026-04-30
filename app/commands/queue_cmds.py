from __future__ import annotations
import difflib
import os
import random
from collections import deque
from discord.ext import commands
from .. import player
from .. import state


# command yang ngurus antrian doang
def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def queue(ctx):
        # nampilin queue asli yang keliatan user
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            tampilan = state.queue_asli.get(guild_id, deque())
            if not tampilan and guild_id not in state.current_playing:
                return await ctx.send("kososng antriannya kek masa depan lu")
            def fi(item):
                if isinstance(item, dict):
                    return item["title"]
                return os.path.basename(item)
            
            now_current_playing = ""
            if guild_id in state.current_playing:
                current = state.current_playing[guild_id]
                if isinstance(current, dict):
                    now_current_playing = f"SABAR INI LAGI PLAY {current['title']}\n\n"
                else:
                    now_current_playing = f"SABAR INI AGI PLAY {os.path.basename(current)}\n\n"
            formatted = "\n".join([f"{i+1}. {fi(f)}" for i, f in enumerate(tampilan)])
            await ctx.send(f"{now_current_playing}nih antirannya\n{formatted if formatted else '(kosong)'}")

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
                return await ctx.send("shuffle nya mati, gw balikin ya urutannya")
            yg_dateng = list(state.queue_asli[guild_id])
            if not yg_dateng:
                return await ctx.send("isi antriannya dongok, yakali ngocok 1 lagu")
            random.shuffle(yg_dateng)
            state.play_queue[guild_id] = deque(yg_dateng)
            state.is_shuffle[guild_id] = True
            state.flag_shuffle[guild_id] = True
            return await ctx.send("gw kocok yaa antriannya, gausah nyesel klo muter yg aneh")

    @bot.command()
    async def remove(ctx, *, target):
        # hapus item queue, bisa by angka atau nama
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)

            if not state.queue_asli.get(guild_id):
                return await ctx.send("Antrian kosong kek masa depan lu")
            
            def item_name(item):
                if isinstance(item, dict):
                    return item.get ("title", "unknown yt title")
                return os.path.basename(item)
            
            def item_key(item):
                """
                Dipake buat pencarian:
                -YT: title
                -Local: basename + name file tanpa ekstensi
                """
                if isinstance(item, dict):
                    title = item.get("title", "")
                    return title.lower().strip()
                base = os.path.basename(item).lower().strip()
                stem = os.path.splitext(base)[0]
                return f"{base} {stem}"

            if target.isdigit():
                pos = int(target) - 1
                if pos < 0 or pos >= len(state.queue_asli[guild_id]):
                    return await ctx.send("salah angka lu nya")

                removed = state.queue_asli[guild_id][pos]
                del state.queue_asli[guild_id][pos]
                try:
                    state.play_queue[guild_id].remove(removed)
                except ValueError:
                    pass
                return await ctx.send(f"gw hapus ya: {item_name(removed)}")

            target_ = target.lower().strip()
            exact_matches = []
            substring_matches = []
            for i, item in enumerate(list(state.queue_asli[guild_id])):
                key = item_key(item)
                if target_ == key or target_ == os.path.basename(item).lower().strip() if not isinstance(item, dict) else target_ == item.get("title", "").lower().strip():
                    exact_matches.append((i, item))
                elif target_ in key:
                    substring_matches.append((i, item))

            if len(exact_matches) == 1:
                idx, removed_item = exact_matches[0]
                del state.queue_asli[guild_id][idx]
                try:
                    state.play_queue[guild_id].remove(removed_item)
                except ValueError:
                    pass
                return await ctx.send(f"gw hapus ya: {item_name(removed_item)}")
            if len(exact_matches) > 1:
                lines = [f"{j+1}. {item_name(p)}" for j, (_, p) in enumerate(exact_matches)]
                return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))
            if len(substring_matches) == 1:
                idx, removed_item = substring_matches[0]
                del state.queue_asli[guild_id][idx]
                try:
                    state.play_queue[guild_id].remove(removed_item)
                except ValueError:
                    pass
                return await ctx.send(f"gw hapus ya: {item_name(removed_item)}")
            if len(substring_matches) > 1:
                lines = [f"{j+1}. {item_name(p)}" for j, (_, p) in enumerate(substring_matches)]
                return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))

            semua_nama = [item_key(f).strip()for f in state.queue_asli[guild_id]]
            kandidat = difflib.get_close_matches(target_, semua_nama, n=5, cutoff=0.3)

            if kandidat:
                # cari saran manual, pendek aja jadi gapapa muter dua loop
                saran_lines = []
                for k in kandidat:
                    for f in state.queue_asli[guild_id]:
                        if item_key(f).strip() == k:
                            saran_lines.append(f"- {item_name(f)}")
                            break
                saran = "\n".join(saran_lines)
                return await ctx.send(f"ga nemu '{target}', maksud lu yg ini?\n{saran}")
            return await ctx.send("ga ketemu antriannya, pmo mulu sih jadi lupa antriannya sendiri")

    @bot.command()
    async def clear(ctx):
        # ngosongin dua queue sekalian
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            if not state.queue_asli[guild_id] and not state.play_queue[guild_id]:
                return await ctx.send("ngapain ongok gada antrian bjir")
            state.queue_asli[guild_id].clear()
            state.play_queue[guild_id].clear()
            await ctx.send("gw hapus nih, gusah nyesel")
