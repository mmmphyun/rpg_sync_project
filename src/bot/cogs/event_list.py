import os
import discord
import aiohttp
import asyncio
import json
import re

from discord.ext import commands
from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration
from src.database.connection import sync_jobs_to_db, sync_job_patch_to_db, sync_users_to_db
from src.database.jobs import update_job_illustrations
from src.database.board import upsert_notice, get_notice_images_by_message_id
from src.bot.utils.s3_client import upload_to_r2, delete_from_r2


class EventList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        try:
            self.patch_channel_id = int(os.getenv('JOB_PATCH_CHANNEL_ID', 0)) or None
            self.desc_thread_id = int(os.getenv('JOB_DESC_THREAD_ID', 0)) or None
            self.illust_thread_id = int(os.getenv('JOB_ILLUST_THREAD_ID', 0)) or None
            self.owner_notice_channel_id = int(os.getenv('OWNER_NOTICE_CHANNEL_ID', 0)) or None
            self.staff_notice_channel_id = int(os.getenv('STAFF_NOTICE_CHANNEL_ID', 0)) or None
        except ValueError as e:
            print(f"[Critical] Failed to parse target channels: {e}")
            self.patch_channel_id = self.desc_thread_id = self.illust_thread_id = None
            self.owner_notice_channel_id = self.staff_notice_channel_id = None

        print(
            f"[System] Targets Loaded - Patch: {self.patch_channel_id}, Desc: {self.desc_thread_id}, Illust: {self.illust_thread_id}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """이벤트 라우팅: 신규 등록"""
        if message.author.bot:
            return

        if message.channel.id not in (
                self.patch_channel_id, self.desc_thread_id, self.illust_thread_id,
                self.owner_notice_channel_id, self.staff_notice_channel_id
        ):
            return

        print(f"[Debug] 타겟 채널 메시지 감지 - 채널ID: {message.channel.id}, 내용: {message.content[:20]}")
        await self._route_event(message)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """캐시되지 않은 기존 메시지(포스트 본문)가 수정될 때 트리거"""
        print(f"[Debug] 수정 이벤트 감지 - 채널ID: {payload.channel_id}, 메시지ID: {payload.message_id}")

        channel_id = payload.channel_id

        # 대상 채널(쓰레드)이 아니면 조기 반환
        if channel_id not in (
                self.patch_channel_id, self.desc_thread_id, self.illust_thread_id,
                self.owner_notice_channel_id, self.staff_notice_channel_id
        ):
            return

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
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """유저 닉네임 변경 감지 및 단건 동기화"""
        if before.bot:
            return

        if before.display_name == after.display_name:
            return

        # 닉네임 파싱 (양식: 후원등급ㅣ직급ㅣ닉네임ㅣ직업명)
        display_name = after.display_name
        parts = [p.strip() for p in re.split(r'[ㅣ\|]', display_name)]

        job_name = None
        actual_nickname = display_name
        server_role = "유저"

        if len(parts) >= 4:
            server_role = parts[-3]
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
        elif len(parts) == 3:
            server_role = parts[-3]
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
        elif len(parts) == 2:
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
        elif len(parts) == 1:
            actual_nickname = parts[0]

        if not server_role:
            server_role = "유저"
        if job_name and not job_name.strip():
            job_name = None

        user_data = {
            "discord_id": str(after.id),
            "nickname": actual_nickname,
            "server_role": server_role,
            "job_name": job_name
        }

        success_count = await asyncio.to_thread(sync_users_to_db, [user_data])

        if success_count > 0:
            print(f"[Info] 유저 정보 변경 동기화 완료: {before.display_name} -> {after.display_name} ({after.id})")
        else:
            print(f"[Warn] 유저 정보 변경 동기화 실패: {after.display_name} ({after.id})")

    async def _route_event(self, message: discord.Message):
        """채널/쓰레드 식별자에 기반한 핸들러 분기"""
        channel_id = message.channel.id

        if channel_id == self.desc_thread_id:
            await self._process_description(message.content)
        elif channel_id == self.patch_channel_id:
            formatted_date = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            await self._process_patch(message.content, formatted_date, message.id)
        elif channel_id == self.illust_thread_id:
            await self._process_illustration(message.content, message.attachments)
        elif channel_id in (self.owner_notice_channel_id, self.staff_notice_channel_id):
            await self._process_notice(message)

    async def _process_description(self, content: str):
        try:
            parsed_data = parse_job_descriptions(content)
            if parsed_data:
                sync_jobs_to_db(parsed_data)
                print(f"[Info] Description sync completed. Processed: {len(parsed_data)} items.")
        except Exception as e:
            print(f"[Error] Description parsing failed: {e}")

    async def _process_patch(self, content: str, created_at: str, message_id: int):
        try:
            parsed_data = parse_job_patches(content, created_at, message_id)
            if parsed_data:
                sync_job_patch_to_db(parsed_data)
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
                print(f"[Info] Illustration update completed. Job: {job_name}, Affected: {affected}")
            else:
                print(f"[Error] R2 upload failed for all attachments of job: {job_name}")

        except Exception as e:
            print(f"[Error] Illustration processing failed: {e}")

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

async def setup(self):
    await self.add_cog(EventList(self))