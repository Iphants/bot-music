from __future__ import annotations
import difflib
import os
import random
from collections import deque
from discord.ext import commands
from .. import player
from .. import state


def setup(bot: commands.Bot) -> None:
    @bot.command()
    async def queue(ctx):
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            tampilan = state.queue_asli.get(guild_id, deque())
            if not tampilan and guild_id not in state.current_playing:
                return await ctx.send("kososng antriannya kek masa depan lu")
            now_current_playing = ""
            if guild_id in state.current_playing:
                now_current_playing = f"SABAR INI LAGI PLAY {os.path.basename(state.current_playing[guild_id])}\n\n"
            formatted = "\n".join([f"{i+1}. {os.path.basename(f)}" for i, f in enumerate(tampilan)])
            await ctx.send(f"{now_current_playing}nih antirannya\n{formatted if formatted else '(kosong)'}")

    @bot.command()
    async def shuffle(ctx):
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
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            player.ensure_deques(guild_id)
            if not state.queue_asli.get(guild_id):
                return await ctx.send("Antrian kosong kek masa depan lu")
            if target.isdigit():
                pos = int(target) - 1
                if pos < 0 or pos >= len(state.queue_asli[guild_id]):
                    return await ctx.send("salah angka lu nya")
                removed = state.queue_asli[guild_id][pos]
                del state.queue_asli[guild_id][pos]
                try:
                    state.play_queue[guild_id].remove(removed)
                except Exception:
                    pass
                return await ctx.send(f"gw hapus ya: {os.path.basename(removed)}")

            target_ = target.lower().strip()
            exact_matches = []
            substring_matches = []
            for i, file_path in enumerate(list(state.queue_asli[guild_id])):
                base = os.path.basename(file_path)
                base_low = base.lower()
                name_no_ext = os.path.splitext(base_low)[0]
                if target_ == base_low or target_ == name_no_ext:
                    exact_matches.append((i, file_path))
                elif target_ in base_low or target_ in name_no_ext:
                    substring_matches.append((i, file_path))
            if len(exact_matches) == 1:
                idx, removed_path = exact_matches[0]
                del state.queue_asli[guild_id][idx]
                try:
                    state.play_queue[guild_id].remove(removed_path)
                except Exception:
                    pass
                return await ctx.send(f"gw hapus ya: {os.path.basename(removed_path)}")
            elif len(exact_matches) > 1:
                lines = [f"{j+1}. {os.path.basename(p)}" for j, (_, p) in enumerate(exact_matches)]
                return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))
            if len(substring_matches) == 1:
                idx, removed_path = substring_matches[0]
                del state.queue_asli[guild_id][idx]
                try:
                    state.play_queue[guild_id].remove(removed_path)
                except Exception:
                    pass
                return await ctx.send(f"gw hapus ya: {os.path.basename(removed_path)}")
            elif len(substring_matches) > 1:
                lines = [f"{j+1}. {os.path.basename(p)}" for j, (_, p) in enumerate(substring_matches)]
                return await ctx.send("yg mana jir, ada banyak, hapus make angka:\n" + "\n".join(lines))

            semua_nama = [os.path.splitext(os.path.basename(f))[0].lower() for f in state.queue_asli[guild_id]]
            kandidat = difflib.get_close_matches(target_, semua_nama, n=5, cutoff=0.3)
            if kandidat:
                saran_lines = []
                for k in kandidat:
                    for f in state.queue_asli[guild_id]:
                        if os.path.splitext(os.path.basename(f))[0].lower() == k:
                            saran_lines.append(f"- {os.path.basename(f)}")
                            break
                saran = "\n".join(saran_lines)
                return await ctx.send(f"ga nemu '{target}', maksud lu yg ini?\n{saran}")
            return await ctx.send("ga ketemu antriannya, pmo mulu sih jadi lupa antriannya sendiri")

    @bot.command()
    async def clear(ctx):
        guild_id = ctx.guild.id
        async with player.kunci_lagu(guild_id):
            if guild_id not in state.queues or not state.queues[guild_id]:
                return await ctx.send("ngapain ongok gada antrian bjir")
            state.queues[guild_id].clear()
            await ctx.send("gw hapus nih, gusah nyesel")

