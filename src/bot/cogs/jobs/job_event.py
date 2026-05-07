import os
import discord
import aiohttp
import asyncio
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration
from src.database.connection import sync_jobs_to_db, sync_job_patch_to_db
from src.database.jobs import update_job_illustrations
from src.database.cache import delete_cache
from src.bot.utils.s3_client import upload_to_r2

class JobEvent(BaseCog):

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """이벤트 라우팅: 신규 등록"""
        if message.author.bot:
            return

        if message.channel.id not in (
                self.patch_channel_id, self.desc_thread_id, self.illust_thread_id
        ):
            return

        print(f"[Debug] 타겟 채널 메시지 감지 - 채널ID: {message.channel.id}, 내용: {message.content[:20]}")
        await self._route_event(message)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """캐시되지 않은 기존 메시지(포스트 본문)가 수정될 때 트리거"""
        channel_id = payload.channel_id

        # 대상 채널(쓰레드)이 아니면 조기 반환
        if channel_id not in (
                self.patch_channel_id, self.desc_thread_id, self.illust_thread_id
        ):
            return

        print(f"[Debug] 수정 이벤트 감지 - 채널ID: {payload.channel_id}, 메시지ID: {payload.message_id}")

        try:
            # 채널 및 메시지 객체를 API를 통해 직접 Fetch
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(payload.message_id)

            if message.author.bot:
                return

            await self._route_event(message)
        except Exception as e:
            print(f"[Error] Raw message fetch failed: {e}")

    async def _route_event(self, message: discord.Message):
        channel_id = message.channel.id

        if channel_id == self.desc_thread_id:
            await self._process_description(message.content)
        elif channel_id == self.patch_channel_id:
            formatted_date = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            await self._process_patch(message.content, formatted_date, message.id)
        elif channel_id == self.illust_thread_id:
            await self._process_illustration(message.content, message.attachments)

    async def _process_description(self, content: str):
        try:
            parsed_data = parse_job_descriptions(content)
            if parsed_data:
                await asyncio.to_thread(sync_jobs_to_db, parsed_data)
                await delete_cache("cache:jobs:all")
                print(f"[Info] Description sync completed. Processed: {len(parsed_data)} items.")
        except Exception as e:
            print(f"[Error] Description parsing failed: {e}")

    async def _process_patch(self, content: str, created_at: str, message_id: int):
        try:
            parsed_data = parse_job_patches(content, created_at, message_id)
            if parsed_data:
                await asyncio.to_thread(sync_job_patch_to_db, parsed_data)
                await delete_cache("cache:jobs:all")
                print(f"[Info] Patch note sync completed for job: {parsed_data.get('name')}")
        except Exception as e:
            print(f"[Error] Patch note processing failed: {e}")

    async def _process_illustration(self, content: str, attachments: list[discord.Attachment]):
        try:
            job_name = parse_job_illustration(content)

            if not job_name:
                print("[Warn] Illustration sync failed: Job name could not be parsed.")
                return
            if not attachments:
                print(f"[Warn] Illustration sync failed: No attachments found for '{job_name}'.")
                return

            ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

            uploaded_urls = []
            async with aiohttp.ClientSession() as session:
                for att in attachments[:4]:
                    if att.content_type not in ALLOWED_MIME_TYPES:
                        print(f"[Warn] 허용되지 않은 파일 형식 차단: {att.filename} ({att.content_type})")
                        continue

                    async with session.get(att.url) as resp:
                        if resp.status == 200:
                            file_bytes = await resp.read()

                            # boto3 동기 함수 호출로 인한 이벤트 루프 블로킹 방지
                            public_url = await asyncio.to_thread(
                                upload_to_r2,
                                file_bytes,
                                att.filename,
                                att.content_type
                            )
                            if public_url:
                                uploaded_urls.append(public_url)

            if uploaded_urls:
                affected = update_job_illustrations(job_name, uploaded_urls)
                await delete_cache("cache:jobs:all")
                print(f"[Info] Illustration update completed. Job: {job_name}, Affected: {affected}")
            else:
                print(f"[Error] R2 upload failed for all attachments of job: {job_name}")

        except Exception as e:
            print(f"[Error] Illustration processing failed: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(JobEvent(bot))