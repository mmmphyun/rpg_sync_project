import os
from discord.ext import commands


class BaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # 공통 타겟 채널 ID 캐싱
        try:
            self.patch_channel_id = int(os.getenv('JOB_PATCH_CHANNEL_ID', 0)) or None
            self.desc_thread_id = int(os.getenv('JOB_DESC_THREAD_ID', 0)) or None
            self.illust_thread_id = int(os.getenv('JOB_ILLUST_THREAD_ID', 0)) or None
            self.owner_notice_channel_id = int(os.getenv('OWNER_NOTICE_CHANNEL_ID', 0)) or None
            self.staff_notice_channel_id = int(os.getenv('STAFF_NOTICE_CHANNEL_ID', 0)) or None
            self.system_patch_channel_id = int(os.getenv('SYSTEM_PATCH_CHANNEL_ID', 0)) or None
            self.build_forum_id = int(os.getenv('BUILD_FORUM_ID', 0)) or None
            self.guild_forum_id = int(os.getenv('GUILD_FORUM_ID', 0)) or None
        except ValueError as e:
            print(f"[Critical] BaseCog env parse error: {e}")
            self.patch_channel_id = self.desc_thread_id = self.illust_thread_id = None
            self.owner_notice_channel_id = self.staff_notice_channel_id = None

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        # 전역 커맨드 에러 핸들러
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("[Error] 해당 명령어 실행 권한이 없습니다.")
        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send("[Error] 명령어 처리 중 서버 내부 오류가 발생했습니다.")
            if hasattr(self.bot, 'send_error_log'):
                import traceback
                orig_err = error.original
                tb_str = "".join(traceback.format_exception(type(orig_err), orig_err, orig_err.__traceback__))
                await self.bot.send_error_log(f"Exception in cog command '{ctx.command.name}':\n{tb_str}")
        else:
            print(f"[Command Error] {ctx.command.name if ctx.command else 'Unknown'}: {error}")