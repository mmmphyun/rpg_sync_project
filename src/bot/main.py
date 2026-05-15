import os
import sys
import traceback
import discord
import asyncio
import concurrent.futures
from discord.ext import commands
from dotenv import load_dotenv
from src.database.cache import init_redis_pool

# 환경변수 로드
load_dotenv()


class RPGSyncBot(commands.Bot):
    def __init__(self):
        # Intents 설정: 메시지 내용과 멤버 정보 접근 권한 필요
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.error_channel_id = int(os.getenv('ERROR_LOG_CHANNEL_ID', 0)) or None
        self.tree.on_error = self.on_app_command_error

    async def send_error_log(self, error_content: str):
        """에러 관제 채널로 트레이스백 발송. Discord 메시지 제한(2000자) 고려하여 Truncate 처리."""
        if not self.error_channel_id:
            return

        channel = self.get_channel(self.error_channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(self.error_channel_id)
            except discord.NotFound:
                return

        if len(error_content) > 1900:
            error_content = error_content[:1900] + "\n... [Truncated]"

        await channel.send(f"```py\n{error_content}\n```")

    async def on_error(self, event_method: str, /, *args, **kwargs):
        """봇 이벤트(on_ready, on_message 등) 루프 내 Uncaught Exception 관제탑 전송"""
        exc_info = sys.exc_info()
        tb_str = "".join(traceback.format_exception(*exc_info))
        error_msg = f"Exception in bot event '{event_method}':\n{tb_str}"

        print(error_msg, file=sys.stderr)
        await self.send_error_log(error_msg)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Prefix 커맨드 실행 중 발생한 예외 전역 캐치"""
        if isinstance(error, commands.CommandNotFound):
            return

        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        error_msg = f"Exception in prefix command '{ctx.command}':\n{tb_str}"

        print(error_msg, file=sys.stderr)
        await self.send_error_log(error_msg)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Slash 커맨드 실행 중 발생한 예외 전역 캐치 및 유저 Fallback 응답"""
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        cmd_name = interaction.command.name if interaction.command else "Unknown"
        error_msg = f"Exception in slash command '{cmd_name}':\n{tb_str}"

        print(error_msg, file=sys.stderr)
        await self.send_error_log(error_msg)

        user_msg = "시스템 내부 오류가 발생했습니다. 관리자에게 문의하세요."
        if not interaction.response.is_done():
            await interaction.response.send_message(user_msg, ephemeral=True)
        else:
            await interaction.followup.send(user_msg, ephemeral=True)

    async def setup_hook(self):
        """봇 구동 시 필요한 확장 모듈을 로드하고 명령어를 동기화합니다."""
        try:
            await init_redis_pool()
            print("Redis connection pool initialized for Bot.", flush=True)
        except Exception as e:
            print(f"Failed to initialize Redis pool: {e}", flush=True)

        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        loop.set_default_executor(executor)
        print("Thread pool executor configured with max_workers=20", flush=True)

        extensions = [
            "src.bot.cogs.auth.auth_cmd",
            "src.bot.cogs.jobs.job_cmd",
            "src.bot.cogs.jobs.job_event",
            "src.bot.cogs.board.board_cmd",
            "src.bot.cogs.board.board_event",
            "src.bot.cogs.board.tip_event",
            "src.bot.cogs.users.user_event",
            "src.bot.cogs.system.bulk_sync_cmd",
            "src.bot.cogs.system.banner_cmd"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"Loaded extension: {ext}", flush=True)
            except Exception as e:
                print(f"Failed to load extension {ext}: {e}", flush=True)

        # 슬래시 명령어 동기화
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)", flush=True)
        except Exception as e:
            print(f"Failed to sync commands: {e}", flush=True)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})', flush=True)
        print('------', flush=True)


if __name__ == '__main__':
    bot = RPGSyncBot()
    discord_token = os.getenv('DISCORD_TOKEN')

    if not discord_token:
        raise ValueError("DISCORD_TOKEN이 .env 파일에 설정되지 않았습니다.")

    bot.run(discord_token)