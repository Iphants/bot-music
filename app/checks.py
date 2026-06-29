from __future__ import annotations
from discord.ext import commands

# nama role yang boleh akses command sensitif bareng owner/admin
DJ_ROLE_NAMES = {"dj", "musik", "music"}

# decorator ini dipakai command !refresh, !clear, dan !volume
def is_dj_or_admin():
    # predicate dipanggil discord.py sebelum command sensitif dieksekusi
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        if await ctx.bot.is_owner(ctx.author):
            return True
        perms = ctx.author.guild_permissions
        if perms.manage_guild or perms.administrator:
            return True
        role_user = {r.name.lower() for r in getattr(ctx.author, "roles", [])}
        if role_user & DJ_ROLE_NAMES:
            return True
        raise commands.CheckFailure("butuh role DJ atau izin admin server")
    return commands.check(predicate)
