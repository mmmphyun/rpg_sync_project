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
        except ValueError as e:
            print(f"[Critical] BaseCog env parse error: {e}")
            self.patch_channel_id = self.desc_thread_id = self.illust_thread_id = None
            self.owner_notice_channel_id = self.staff_notice_channel_id = None

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        # 전역 커맨드 에러 핸들러
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("[Error] 해당 명령어 실행 권한이 없습니다.")
        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send(f"[Error] 명령어 실행 중 예외 발생: {error.original}")
        else:
            print(f"[Command Error] {ctx.command.name if ctx.command else 'Unknown'}: {error}")