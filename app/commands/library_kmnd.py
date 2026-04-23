from __future__ import annotations
import discord
from discord import ui
from discord.ext import commands
from .. import config
from .. import state

AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".m4a")
PER_PAGE = 25
ROOT = config.music_root_dir().resolve()

# ===== SCAN LIBRARY =====
def _scan_library_dir(base):
    base = base.resolve()
    folders = []
    files = []

    for item in base.iterdir():
        if item.is_dir():
            folders.append(item.name)
        elif item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
            files.append(item.name)

    folders.sort()
    files.sort()
    return folders, files

# ===== SIMPAN FOLDER =====
def _set_last_folder(author_id, base, folders, files, page=0):
    state.folder_terakhir[author_id] = {"base": base.resolve(), "folders": folders, "files": files, "page": page, }

# ===== HISTORY FOLDER =====
def push_history(author_id, base):
    history = state.folder_history.setdefault(author_id, [])
    base = base.resolve()
    if not history or history[-1] != base:
        history.append(base)
    
def pop_history(author_id):
    history = state.folder_history.get(author_id)
    if not history:
        return None
    if len(history) == 0:
        return None
    return history.pop()

# ===== PAGINASI =====
def _all_items(folders, files):
    return [("folder", f) for f in folders] + [("file", f) for f in files]

def page_items(folders, files, page = 0, per_page=PER_PAGE):
    items = _all_items(folders, files)
    total = len(items)
    max_page = max(1, (total - 1) // per_page + 1)
    page = max (0, min(page, max_page - 1))  # clamp manual aja
    start = page * per_page
    end = start + per_page
    visible_items = items[start:end]
    return visible_items, total, max_page, start, page

# ===== EMBED LIBRARY =====
def build_library_embed(base, folders, files, page=0, per_page=PER_PAGE):
    base = base.resolve()
    visible_items, total, max_page, start, page = page_items(folders, files, page=page, per_page=per_page)
    lines = []

    for i, (kind, name) in enumerate(visible_items, start=start + 1):
        icon = "📁" if kind == "folder" else "🎵"
        lines.append(f"{i}. {icon} {name}")

    teks = "\n".join(lines) if lines else "kosong jir"
    title = base.name if base != ROOT else "Root"

    embed = discord.Embed(
        title=f"Library: {title}",
        description=teks,
        color=0x41639b,
    )
    embed.set_footer(text=f"Halaman {page + 1}/{max_page}")
    return embed

# ===== VIEW LIBRARY =====
class LibraryView(ui.View):
    def __init__(self, ctx, base, folders, files, page=0, per_page=PER_PAGE):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.base = base.resolve()
        self.folders = folders
        self.files = files
        self.page = page
        self.per_page = per_page
        self.message = None
        self.visible_items = []
        self.refresh_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message(
            "ini library orang lain, buka sendiri pake !library",
            ephemeral=True,
        )
        return False

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    def refresh_components(self):
        self.clear_items()

        items = _all_items(self.folders, self.files)
        total = len(items)
        max_page = max(1, (total - 1) // self.per_page + 1)
        self.page = max(0, min(self.page, max_page - 1))
        start = self.page * self.per_page
        end = start + self.per_page
        self.visible_items = items[start:end]

        if self.visible_items:
            options = []
            for idx, (kind, name) in enumerate(self.visible_items):
                label = f"{start + idx + 1}. {name}"
                # discord cuma mau 100 char, yaudah potong aja
                options.append(
                    discord.SelectOption(
                        label=label[:100],
                        value=str(idx),
                        emoji="📁" if kind == "folder" else "🎵",
                    )
                )

            select = ui.Select(
                placeholder="Pilih folder atau lagu",
                options=options,
                min_values=1,
                max_values=1,
            )
            select.callback = self.on_select
            self.add_item(select)

        print(f"[BACK DEBUG] base={self.base}")
        print(f"[BACK DEBUG] root={ROOT}")

        self.add_item(LibraryPrevButton(disabled=self.page <= 0))
        self.add_item(LibraryBackButton(disabled=self.base == ROOT))
        self.add_item(LibraryNextButton(disabled=self.page >= max_page - 1))

    async def on_select(self, interaction: discord.Interaction):
        idx = int(interaction.data["values"][0])
        kind, name = self.visible_items[idx]

        if kind == "folder":
            new_base = (self.base / name).resolve()
            push_history(self.ctx.author.id, self.base)
            folders, files = _scan_library_dir(new_base)
            _set_last_folder(self.ctx.author.id, new_base, folders, files, page=0)

            new_view = LibraryView(self.ctx, new_base, folders, files, page=0)
            embed = build_library_embed(new_base, folders, files, page=0)
            await interaction.response.edit_message(embed=embed, view=new_view)
            self.stop()
            new_view.message = interaction.message
            return

        rel = (self.base / name).resolve().relative_to(ROOT)
        await interaction.response.defer()
        await self.ctx.invoke(self.ctx.bot.get_command("play"), nama_file=str(rel))


# ===== BUTTON BACK =====
class LibraryBackButton(ui.Button):
    def __init__(self, disabled=False):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, disabled=disabled,)

    async def callback(self, interaction: discord.Interaction):
        print("[BUTTON CLICKED] Back")
        view = self.view
        author_id = view.ctx.author.id
        previous = pop_history(author_id)

        if previous is None:
            if view.base == ROOT:
                await interaction.response.send_message("dh di root", ephemeral=True)
                return
            previous = view.base.parent.resolve()
            if previous != ROOT and not str(previous).startswith(str(ROOT)):
                previous = ROOT
        
        folders, files = _scan_library_dir(previous) 
        _set_last_folder(author_id, previous, folders, files, page=0)

        new_view = LibraryView(view.ctx, previous, folders, files, page=0)
        embed = build_library_embed(previous, folders, files, page=0)

        await interaction.response.edit_message(embed=embed, view=new_view)
        view.stop()
        new_view.message = interaction.message

# ===== BUTTON PREV =====
class LibraryPrevButton(ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            label="Prev",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        print("[BUTTON CLICKED] Prev")
        view = self.view
        new_page = view.page - 1

        _set_last_folder(view.ctx.author.id, view.base, view.folders, view.files, page=new_page)

        new_view = LibraryView(view.ctx, view.base, view.folders, view.files, page=new_page, per_page=view.per_page,)
        embed = build_library_embed(view.base, view.folders, view.files, page=new_page,per_page=view.per_page,)

        await interaction.response.edit_message(embed=embed, view=new_view)
        view.stop()
        new_view.message = interaction.message

# ===== BUTTON NEXT =====
class LibraryNextButton(ui.Button):
    def __init__(self, disabled=False):
        super().__init__(
            label="Next",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        print("[BUTTON CLICKED] Next")
        view = self.view
        new_page = view.page + 1
        _set_last_folder(view.ctx.author.id, view.base, view.folders, view.files, page=new_page)
        new_view = LibraryView(view.ctx, view.base,view.folders, view.files, page=new_page,per_page=view.per_page,)
        embed = build_library_embed(view.base, view.folders, view.files, page=new_page, per_page=view.per_page,)
        await interaction.response.edit_message(embed=embed, view=new_view)
        view.stop()
        new_view.message = interaction.message

# ===== COMMAND LIBRARY =====
def setup(bot: commands.Bot):
    @bot.command()
    async def library(ctx, page: int = 1):
        # ===== BUKA LIBRARY =====
        base = ROOT
        folders, files = _scan_library_dir(base)
        _set_last_folder(ctx.author.id, base, folders, files)
        state.folder_history[ctx.author.id] = []
        total = len(folders) + len(files)
        max_page = max(1, (total - 1) // PER_PAGE + 1)
        if page < 1 or page > max_page:
            await ctx.send(f"halaman 1 - {max_page}")
            return
        
        _set_last_folder(ctx.author.id, base, folders, files, page=page- 1)
        view = LibraryView(ctx, base, folders, files, page=page - 1)
        embed = build_library_embed(base, folders, files, page=page - 1)
        view.message = await ctx.send(embed=embed, view=view)
    
    @bot.command()
    async def open(ctx, nomor: int):
        # ===== OPEN ITEM =====
        data = state.folder_terakhir.get(ctx.author.id)

        if not data:
            await ctx.send("lu blom buka library")
            return
        
        base = data["base"]
        folders = data["folders"]
        files = data["files"]
        page = data.get("page", 0)
        visible_items, total, max_page, start, page = page_items(folders, files, page=page, per_page=PER_PAGE)

        if not visible_items:
            await ctx.send("kosong jir")
            return
        
        start_nomr = start + 1
        end_nomr = start + len(visible_items)
        
        if nomor < start_nomr or nomor > end_nomr:
            await ctx.send(f"nomor cuma yang lagi keliatan: {start_nomr}-{end_nomr}")
            return
        
        kind, name = visible_items[nomor - start_nomr]

        if kind == "folder":
            new_base = (base / name).resolve()
            push_history(ctx.author.id, base)
            folders, files = _scan_library_dir(new_base)
            _set_last_folder(ctx.author.id, new_base, folders, files, page=0)
            view = LibraryView(ctx, new_base, folders, files, page=0)
            embed = build_library_embed(new_base, folders, files, page=0)
            view.message = await ctx.send(embed=embed, view=view)
            return
        
        file_path = (base / name).resolve()
        try:
            rel = file_path.relative_to(ROOT)
        except ValueError:
            await ctx.send("file nya di luar root musik")
            return
        if not file_path.exists():
            await ctx.send("file nya dah gada")
            return
        await ctx.invoke(bot.get_command("play"), nama_file=str(rel))

    @bot.command()
    async def back (ctx):
        # ===== BACK FOLDER =====
        data = state.folder_terakhir.get(ctx.author.id)

        if not data:
            await ctx.send("lu blom buka apa-apa")
            return
        
        previous = pop_history(ctx.author.id)
        
        if previous is None:
            if data["base"].resolve() == ROOT:
                await ctx.send("dh di root")
                return
            previous = data["base"].parent.resolve()
            if previous != ROOT and not str(previous).startswith(str(ROOT)):
                previous = ROOT

        folders, files = _scan_library_dir(previous)
        _set_last_folder(ctx.author.id, previous, folders, files, page=0)

        view = LibraryView(ctx, previous, folders, files, page=0)
        embed = build_library_embed(previous, folders, files, page=0)
        view.message = await ctx.send(embed=embed, view=view)
