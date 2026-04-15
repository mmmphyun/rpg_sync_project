import os
import discord
from discord.ext import commands
from src.bot.utils.text_parser import parse_discord_jobs
from src.database.connection import sync_jobs_to_db


class EventList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # .env에서 감지 대상 채널 ID 로드
        target_id = os.getenv('TARGET_CHANNEL_ID')
        self.target_channel_id = int(target_id) if target_id else None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """새로운 메시지(포스트)가 등록될 때 트리거"""
        if message.author.bot or not self.target_channel_id:
            return

        if message.channel.id == self.target_channel_id:
            await self._process_job_post(message.content)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """기존 메시지(포스트)가 수정될 때 트리거"""
        if after.author.bot or not self.target_channel_id:
            return

        # 메시지 내용이 실제로 변경된 경우에만 처리
        if before.content == after.content:
            return

        if after.channel.id == self.target_channel_id:
            await self._process_job_post(after.content)

    async def _process_job_post(self, content: str):
        """메시지 원문을 파싱하고 데이터베이스에 병합(UPSERT) 처리"""
        try:
            parsed_data = parse_discord_jobs(content)
            if parsed_data:
                sync_jobs_to_db(parsed_data)
                print(f"[{len(parsed_data)}]건의 직업 데이터 파싱 및 DB 동기화 완료.")
            else:
                print("파싱된 직업 데이터가 없습니다.")
        except Exception as e:
            print(f"데이터 처리 중 오류 발생: {e}")


async def setup(self):
    """Cog 로드 엔트리 포인트"""
    await self.add_cog(EventList(self))