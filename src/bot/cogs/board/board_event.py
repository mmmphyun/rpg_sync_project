import os
import discord
import aiohttp
import asyncio
import json
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.database.board import upsert_notice, get_notice_images_by_message_id, delete_notice_by_message_id
from src.bot.utils.s3_client import upload_to_r2, delete_from_r2

class BoardEvent(BaseCog):

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """이벤트 라우팅: 신규 등록"""
        if message.author.bot:
            return

        if message.channel.id not in (
                self.owner_notice_channel_id, self.staff_notice_channel_id
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
                self.owner_notice_channel_id, self.staff_notice_channel_id
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

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """공지/이벤트 게시글 삭제 감지 및 Soft Delete 적용"""
        if payload.channel_id not in (self.owner_notice_channel_id, self.staff_notice_channel_id):
            return

        try:
            # DB Soft Delete 처리 및 연동된 기존 이미지 URL 반환
            deleted_image_urls = await asyncio.to_thread(delete_notice_by_message_id, str(payload.message_id))

            if deleted_image_urls:
                for image_url in deleted_image_urls:
                    await asyncio.to_thread(delete_from_r2, image_url)
                print(f"[Info] 게시글 삭제 동기화 완료: Message ID {payload.message_id}")

        except Exception as e:
            print(f"[Error] 게시글 삭제 동기화 실패: {e}")

    async def _route_event(self, message: discord.Message):
        """채널/쓰레드 식별자에 기반한 핸들러 분기"""
        channel_id = message.channel.id

        if channel_id in (self.owner_notice_channel_id, self.staff_notice_channel_id):
            await self._process_notice(message)

    async def _process_notice(self, message: discord.Message):
        try:
            # 1. 기존 데이터 조회
            old_image_urls = get_notice_images_by_message_id(message.id)

            ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

            uploaded_urls = []

            # 2. 현재 첨부파일 R2 업로드
            if message.attachments:
                async with aiohttp.ClientSession() as session:
                    for att in message.attachments:
                        if att.content_type not in ALLOWED_MIME_TYPES:
                            print(f"[Warn] 허용되지 않은 파일 형식 차단: {att.filename} ({att.content_type})")
                            continue

                        async with session.get(att.url) as resp:
                            if resp.status == 200:
                                file_bytes = await resp.read()

                                public_url = await asyncio.to_thread(
                                    upload_to_r2,
                                    file_bytes,
                                    att.filename,
                                    att.content_type,
                                    "notices"
                                )
                                if public_url:
                                    uploaded_urls.append(public_url)

            # 3. DB UPSERT
            clean_content = message.content.replace('```', '')

            notice_data = {
                'type': 'notice',
                'tag': '일반 공지',
                'content': clean_content,
                'image_urls': json.dumps(uploaded_urls),
                'discord_message_id': str(message.id),
                'author_id': str(message.author.id),
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }

            affected = upsert_notice(notice_data)

            # 4. UPSERT 성공 시 기존 R2 이미지 일괄 삭제
            if affected > 0 and old_image_urls:
                for old_url in old_image_urls:
                    await asyncio.to_thread(delete_from_r2, old_url)

            print(f"[Info] Notice sync completed. Message ID: {message.id}, Affected: {affected}")

        except Exception as e:
            print(f"[Error] Notice processing failed: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(BoardEvent(bot))