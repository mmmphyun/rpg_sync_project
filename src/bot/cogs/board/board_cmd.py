import discord
import os
import asyncio

from discord.ext import commands
from discord import app_commands
from src.database.board import update_notice_title
from src.database.cache import delete_cache
from src.bot.utils.checks import has_staff_privilege

VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

def is_valid_image(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in VALID_IMAGE_EXTENSIONS

class BoardCmd(commands.GroupCog, name="공지"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="제목", description="지정한 공지 메시지의 제목을 변경합니다.")
    @app_commands.describe(
        message_id="변경할 공지 메시지의 ID",
        title="변경할 새로운 공지 제목 (최대 200자)"
    )
    @app_commands.guild_only()
    @has_staff_privilege()
    async def set_notice_title(self, interaction: discord.Interaction, message_id: str, title: str):
        await interaction.response.defer(thinking=True)

        try:
            if len(title) > 200:
                await interaction.followup.send("제목이 너무 깁니다. (최대 200자)")
                return

            success = await asyncio.to_thread(update_notice_title, message_id, title)
            if success:
                # 캐시 무효화 추가
                await delete_cache("cache:main_page:all")
                await delete_cache("cache:boards:notice:page:1:tag:None")
                await delete_cache("cache:boards:event:page:1:tag:None")
                await interaction.followup.send(f"성공적으로 제목이 업데이트되었습니다: **{title}**")
            else:
                await interaction.followup.send("해당 메시지 ID를 가진 공지를 찾을 수 없습니다.")
        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '공지 제목':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(BoardCmd(bot))