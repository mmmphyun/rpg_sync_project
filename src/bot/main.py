import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()


class RPGSyncBot(commands.Bot):
    def __init__(self):
        # Intents 설정: 메시지 내용과 멤버 정보 접근 권한 필요
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """봇 구동 시 필요한 확장 모듈을 로드하고 명령어를 동기화합니다."""
        extensions = [
            "src.bot.cogs.auth.auth_cmd",
            "src.bot.cogs.jobs.job_cmd",
            "src.bot.cogs.system.bulk_sync_cmd"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"Loaded extension: {ext}")
            except Exception as e:
                print(f"Failed to load extension {ext}: {e}")

        # 슬래시 명령어 동기화
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')


if __name__ == '__main__':
    bot = RPGSyncBot()
    discord_token = os.getenv('DISCORD_TOKEN')

    if not discord_token:
        raise ValueError("DISCORD_TOKEN이 .env 파일에 설정되지 않았습니다.")

    bot.run(discord_token)