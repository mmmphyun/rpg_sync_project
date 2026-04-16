import os
import discord
from discord.ext import commands
from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration
from src.database.connection import sync_jobs_to_db, sync_job_patch_to_db
from src.database.queries import update_job_illustrations


class EventList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # TARGET_CHANNEL_ID 맵핑 규칙: 0=패치노트, 1=직업설명, 2=일러스트
        target_ids_str = os.getenv('TARGET_CHANNEL_IDS', '')
        try:
            # 설정 값 정제 및 int 캐스팅 (IndexError 방지를 위해 할당 전 검증 처리)
            id_list = [int(c_id.strip().replace('"', '').replace("'", ""))
                       for c_id in target_ids_str.split(',') if c_id.strip().isdigit()]

            self.patch_channel_id = id_list[0] if len(id_list) > 0 else None
            self.desc_thread_id = id_list[1] if len(id_list) > 1 else None
            self.illust_thread_id = id_list[2] if len(id_list) > 2 else None
        except Exception as e:
            print(f"[Critical] Failed to parse target channels: {e}")
            self.patch_channel_id = self.desc_thread_id = self.illust_thread_id = None

        print(
            f"[System] Targets Loaded - Patch: {self.patch_channel_id}, Desc: {self.desc_thread_id}, Illust: {self.illust_thread_id}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """이벤트 라우팅: 신규 등록"""
        if message.author.bot:
            return
        await self._route_event(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """이벤트 라우팅: 기존 포스트 수정"""
        if after.author.bot or before.content == after.content:
            return
        await self._route_event(after)

    async def _route_event(self, message: discord.Message):
        """채널 식별자에 기반한 핸들러 분기"""
        channel_id = message.channel.id

        if channel_id == self.desc_thread_id:
            await self._process_description(message.content)
        elif channel_id == self.patch_channel_id:
            await self._process_patch(message.content)
        elif channel_id == self.illust_thread_id:
            await self._process_illustration(message.content, message.attachments)

    async def _process_description(self, content: str):
        try:
            parsed_data = parse_job_descriptions(content)
            if parsed_data:
                sync_jobs_to_db(parsed_data)
                print(f"[Info] Description sync completed. Processed: {len(parsed_data)} items.")
        except Exception as e:
            print(f"[Error] Description parsing failed: {e}")

    async def _process_patch(self, content: str):
        try:
            parsed_data = parse_job_patches(content)
            if parsed_data:
                sync_job_patch_to_db(parsed_data)
                print(f"[Info] Patch note sync completed for job: {parsed_data.get('name')}")
        except Exception as e:
            print(f"[Error] Patch note processing failed: {e}")

    async def _process_illustration(self, content: str, attachments: list[discord.Attachment]):
        try:
            job_name = parse_job_illustration(content)
            if job_name and attachments:
                # 테이블 스키마에 맞춰 최대 4개의 attachment URL 슬라이싱
                image_urls = [att.url for att in attachments[:4]]
                affected = update_job_illustrations(job_name, image_urls)
                print(f"[Info] Illustration update completed. Job: {job_name}, Affected: {affected}")
        except Exception as e:
            print(f"[Error] Illustration processing failed: {e}")


async def setup(self):
    await self.add_cog(EventList(self))