import discord
import os
import asyncio
import mimetypes
from discord.ext import commands
from src.bot.cogs.core.base_cog import BaseCog
from src.database.board import update_notice_title
from src.bot.utils.s3_client import upload_to_r2
from src.database.skills import upsert_weapon_and_skill

VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

def is_valid_image(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in VALID_IMAGE_EXTENSIONS

class BoardCmd(BaseCog):

    @commands.command(name="공지제목")
    @commands.has_permissions(administrator=True)
    async def set_notice_title(self, ctx, message_id: str, *, title: str):
        if len(title) > 200:
            return await ctx.send("제목이 너무 깁니다. (최대 200자)")

        success = update_notice_title(message_id, title)
        if success:
            await ctx.send(f"성공적으로 제목이 업데이트되었습니다: **{title}**")
        else:
            await ctx.send("해당 메시지 ID를 가진 공지를 찾을 수 없습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(BoardCmd(bot))