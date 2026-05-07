import aiohttp
import discord
import asyncio
import json
import re
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.database.tip import upsert_tip, get_tip_images_by_thread_id, delete_tip_by_thread_id
from src.bot.utils.s3_client import upload_to_r2, delete_from_r2
from src.database.cache import delete_cache


class TipEvent(BaseCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    def _extract_youtube_urls(self, content: str) -> list:
        """본문에서 유튜브 링크 추출"""
        youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.?be)/[^\s]+'
        urls = [match.group() for match in re.finditer(youtube_regex, content)]
        return urls

    def _get_category(self, parent_id: int) -> str:
        """포럼 ID를 기준으로 카테고리 판별"""
        if parent_id == getattr(self, 'build_forum_id', None):
            return 'BUILD'
        elif parent_id == getattr(self, 'guild_forum_id', None):
            return 'GUILD'
        return None

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """이벤트 라우팅: 포럼 쓰레드의 최초 게시물 감지"""
        # [디버그 1] 이벤트가 디스코드로부터 정상적으로 수신되는지 확인
        print(f"[Debug] 쓰레드 생성 이벤트 수신 - 부모ID: {thread.parent_id}, 쓰레드명: {thread.name}", flush=True)

        category = self._get_category(thread.parent_id)

        # [디버그 2] 카테고리 매칭에 성공했는지 확인
        print(f"[Debug] 판별된 카테고리: {category}", flush=True)
        if not category:
            return

        try:
            await thread.join()
        except Exception as e:
            print(f"[Warn] Failed to join thread: {e}")

        await asyncio.sleep(1)

        try:
            starter_message = await thread.fetch_message(thread.id)
            if not starter_message.author.bot:
                await self._process_tip(starter_message, category)
        except discord.NotFound:
            print(f"[Warn] Starter message not found for thread {thread.id}")
        except Exception as e:
            print(f"[Error] Thread processing failed: {e}")

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """쓰레드의 최초 메시지(본문) 수정 감지"""
        # 쓰레드 ID와 메시지 ID가 다르면(댓글 수정이면) 무시
        if payload.message_id != payload.channel_id:
            return

        channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        if not isinstance(channel, discord.Thread):
            return

        category = self._get_category(channel.parent_id)
        if not category:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
            if message.author.bot:
                return

            await self._process_tip(message, category)
        except Exception as e:
            print(f"[Error] Tip message fetch failed: {e}")

    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent):
        """디스코드 포럼 쓰레드 삭제 감지"""
        category = self._get_category(payload.parent_id)
        if not category:
            return

        try:
            # DB Soft Delete 처리 및 기존 이미지 삭제
            deleted_image_urls = await asyncio.to_thread(delete_tip_by_thread_id, str(payload.thread_id))

            await delete_cache(f"cache:tips:{category}:page:1")

            if deleted_image_urls:
                for image_url in deleted_image_urls:
                    await asyncio.to_thread(delete_from_r2, image_url)
                print(f"[Info] Tip thread deleted. Thread ID: {payload.thread_id}")

        except Exception as e:
            print(f"[Error] Tip thread deletion sync failed: {e}")

    async def _process_tip(self, message: discord.Message, category: str):
        try:
            thread = message.channel
            title = thread.name

            old_image_urls = await asyncio.to_thread(get_tip_images_by_thread_id, str(thread.id))

            raw_text = str(message.clean_content)

            # 코드블럭 제거
            clean_content = raw_text.replace('```', '').strip()

            # 유튜브 링크 추출
            youtube_urls = self._extract_youtube_urls(clean_content)

            # R2 이미지 업로드 (동영상 파일 제외)
            uploaded_urls = []
            ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

            if message.attachments:
                async with aiohttp.ClientSession() as session:
                    for att in message.attachments:
                        if att.content_type not in ALLOWED_IMAGE_TYPES:
                            continue

                        async with session.get(att.url) as resp:
                            if resp.status == 200:
                                file_bytes = await resp.read()
                                public_url = await asyncio.to_thread(
                                    upload_to_r2,
                                    file_bytes,
                                    att.filename,
                                    att.content_type,
                                    "tips"
                                )
                                if public_url:
                                    uploaded_urls.append(public_url)

            tip_data = {
                'category': category,
                'title': title,
                'content': clean_content,
                'image_urls': json.dumps(uploaded_urls),
                'youtube_urls': json.dumps(youtube_urls),
                'discord_thread_id': str(thread.id),
                'author_id': str(message.author.id)
            }

            affected = await asyncio.to_thread(upsert_tip, tip_data)

            # 성공 시 기존 R2 이미지 일괄 삭제
            if affected > 0:
                await delete_cache(f"cache:tips:{category}:page:1")

                if old_image_urls:
                    for old_url in old_image_urls:
                        await asyncio.to_thread(delete_from_r2, old_url)

            print(f"[Info] Tip sync completed. Thread: {title}, Category: {category}")

        except Exception as e:
            print(f"[Error] Tip processing failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(TipEvent(bot))