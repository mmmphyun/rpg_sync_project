import discord
import os
import re
import asyncio
import aiohttp
import json
from discord import app_commands
from datetime import timedelta, datetime, timezone
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog

from src.database.jobs import update_job_illustrations
from src.database.board import upsert_notice
from src.database.connection import sync_users_to_db, sync_jobs_to_db, sync_job_patch_to_db
from src.database.tip import upsert_tip

from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration
from src.bot.utils.s3_client import upload_to_r2

class BulkSyncCmd(BaseCog):

    @commands.command(name="유저동기화")
    @commands.has_permissions(administrator=True)
    async def sync_users_command(self, ctx: commands.Context):
        """서버 내 전체 유저의 ID, 닉네임, 역할 및 직업을 DB와 동기화합니다."""
        await ctx.send("유저 동기화를 시작합니다.")

        users_data = []
        for member in ctx.guild.members:
            if not member.bot:
                # 닉네임 파싱 (양식: 후원등급ㅣ직급ㅣ닉네임ㅣ직업명)
                display_name = member.display_name
                parts = [p.strip() for p in re.split(r'[ㅣ\|]', display_name)]

                job_name = None
                actual_nickname = display_name
                server_role = "유저"  # 파싱 실패 또는 누락 시 기본값

                if len(parts) >= 4:
                    # [후원등급, 직급, 닉네임, 직업명] (요소가 더 많아도 뒤에서부터 매핑)
                    server_role = parts[-3]
                    actual_nickname = parts[-2]
                    job_name = parts[-1].replace(" ", "").lower()
                elif len(parts) == 3:
                    # [직급, 닉네임, 직업명] (후원등급 누락 케이스)
                    server_role = parts[-3]
                    actual_nickname = parts[-2]
                    job_name = parts[-1].replace(" ", "").lower()
                elif len(parts) == 2:
                    # [닉네임, 직업명]
                    actual_nickname = parts[-2]
                    job_name = parts[-1].replace(" ", "").lower()
                elif len(parts) == 1:
                    # [닉네임]
                    actual_nickname = parts[0]

                # 빈 문자열 처리
                if not server_role:
                    server_role = "유저"
                if job_name and not job_name.strip():
                    job_name = None

                users_data.append({
                    "discord_id": str(member.id),
                    "nickname": actual_nickname,
                    "server_role": server_role,
                    "job_name": job_name
                })

        success_count = await asyncio.to_thread(sync_users_to_db, users_data)
        await ctx.send(f"유저 동기화 완료: 총 {success_count}명의 데이터가 최신화되었습니다.")

    @commands.command(name="데이터동기화")
    @commands.has_permissions(administrator=True)
    async def sync_data_command(self, ctx: commands.Context):
        """각 쓰레드/채널의 과거 게시글을 일괄 파싱하여 DB에 적재합니다."""
        await ctx.send("게시글 일괄 데이터 동기화를 시작합니다.")

        try:
            patch_channel_id = int(os.getenv('JOB_PATCH_CHANNEL_ID', 0))
            desc_thread_id = int(os.getenv('JOB_DESC_THREAD_ID', 0))
            illust_thread_id = int(os.getenv('JOB_ILLUST_THREAD_ID', 0))
        except ValueError:
            await ctx.send("환경 변수에 채널 ID가 올바르게 설정되지 않아 중단합니다.")
            return

        if not all([patch_channel_id, desc_thread_id, illust_thread_id]):
            await ctx.send("필수 채널 ID가 누락되어 중단합니다.")
            return

        # 1. 직업 설명 동기화 (JOBS 테이블 생성)
        desc_channel = self.bot.get_channel(desc_thread_id) or await self.bot.fetch_channel(desc_thread_id)
        desc_count = 0
        if desc_channel:
            async for message in desc_channel.history(limit=None, oldest_first=True):
                if not message.author.bot:
                    parsed_data = parse_job_descriptions(message.content)
                    if parsed_data:
                        await asyncio.to_thread(sync_jobs_to_db, parsed_data)
                        desc_count += len(parsed_data)

        # 2. 패치노트 동기화 (JOB_PATCHES 테이블 생성)
        patch_channel = self.bot.get_channel(patch_channel_id) or await self.bot.fetch_channel(patch_channel_id)
        patch_count = 0
        if patch_channel:
            async for message in patch_channel.history(limit=None, oldest_first=True):
                if not message.author.bot:
                    # 파라미터 주입을 위해 KST 시간 변환 선행 처리
                    kst_time = message.created_at + timedelta(hours=9)
                    patch_date_str = kst_time.strftime('%Y-%m-%d %H:%M:%S')

                    # 파서에 필수 인자(content, created_at, message_id) 모두 전달
                    parsed_data = parse_job_patches(message.content, patch_date_str, message.id)

                    # 파서에서 완전한 딕셔너리를 반환하므로 즉시 DB 동기화
                    if parsed_data:
                        await asyncio.to_thread(sync_job_patch_to_db, parsed_data)
                        patch_count += 1

        # 3. 일러스트 동기화 (JOBS 테이블 PHOTO 업데이트)
        illust_channel = self.bot.get_channel(illust_thread_id) or await self.bot.fetch_channel(illust_thread_id)
        illust_count = 0
        if illust_channel:
            async with aiohttp.ClientSession() as session:
                async for message in illust_channel.history(limit=None, oldest_first=True):
                    if not message.author.bot and message.attachments:
                        job_name = parse_job_illustration(message.content)
                        if job_name:
                            uploaded_urls = []
                            for att in message.attachments[:4]:
                                async with session.get(att.url) as resp:
                                    if resp.status == 200:
                                        file_bytes = await resp.read()

                                        # boto3는 동기 라이브러리이므로 이벤트 루프 블로킹 방지를 위해 to_thread 실행
                                        public_url = await asyncio.to_thread(
                                            upload_to_r2,
                                            file_bytes,
                                            att.filename,
                                            att.content_type
                                        )

                                        if public_url:
                                            uploaded_urls.append(public_url)

                            if uploaded_urls:
                                await asyncio.to_thread(update_job_illustrations, job_name, uploaded_urls)
                                illust_count += 1

        await ctx.send(
            f"일괄 데이터 동기화 완료\n- 파싱된 직업: {desc_count}건\n- 적재된 패치노트: {patch_count}건\n- 연결된 일러스트: {illust_count}건")

    @commands.command(name="공지동기화")
    @commands.has_permissions(administrator=True)
    async def sync_notice_command(self, ctx: commands.Context):
        """디스코드 공지 채널의 2026년 4월 1일 이후 게시글을 DB에 동기화합니다."""
        await ctx.send("공지사항 동기화를 시작합니다.")

        try:
            owner_channel_id = int(os.getenv('OWNER_NOTICE_CHANNEL_ID', 0))
            staff_channel_id = int(os.getenv('STAFF_NOTICE_CHANNEL_ID', 0))
            patch_channel_id = int(os.getenv('SYSTEM_PATCH_CHANNEL_ID', 0))
        except ValueError:
            await ctx.send("환경 변수에 공지 채널 ID가 올바르게 설정되지 않았습니다.")
            return

        if not owner_channel_id and not staff_channel_id:
            await ctx.send("동기화할 공지 채널이 설정되지 않아 중단합니다.")
            return

        target_channels = []
        if owner_channel_id:
            ch = self.bot.get_channel(owner_channel_id) or await self.bot.fetch_channel(owner_channel_id)
            if ch: target_channels.append(ch)
        if staff_channel_id:
            ch = self.bot.get_channel(staff_channel_id) or await self.bot.fetch_channel(staff_channel_id)
            if ch: target_channels.append(ch)
        if patch_channel_id:
            ch = self.bot.get_channel(patch_channel_id) or await self.bot.fetch_channel(patch_channel_id)
            if ch: target_channels.append(ch)

        # 2026년 4월 1일 KST 기준 타임존 설정
        kst_tz = timezone(timedelta(hours=9))
        cutoff_date = datetime(2026, 4, 1, tzinfo=kst_tz)

        sync_count = 0

        async with aiohttp.ClientSession() as session:
            for channel in target_channels:
                # after 파라미터를 사용하여 지정 날짜 이후의 메시지만 가져옴
                async for message in channel.history(limit=None, after=cutoff_date, oldest_first=True):
                    if message.author.bot:
                        continue

                    uploaded_urls = []
                    if message.attachments:
                        for att in message.attachments:
                            async with session.get(att.url) as resp:
                                if resp.status == 200:
                                    file_bytes = await resp.read()
                                    public_url = await asyncio.to_thread(
                                        upload_to_r2,
                                        file_bytes,
                                        att.filename,
                                        att.content_type,
                                        "notices"  # 공지사항용 폴더 지정
                                    )
                                    if public_url:
                                        uploaded_urls.append(public_url)

                    # Discord UTC 시간을 KST로 변환
                    created_at_kst = message.created_at.astimezone(kst_tz)

                    raw_text = str(message.clean_content)
                    clean_content = raw_text.replace('```', '')

                    notice_data = {
                        "type": "notice",
                        "tag": "일반 공지",
                        "content": clean_content,
                        "image_urls": json.dumps(uploaded_urls),
                        "discord_message_id": str(message.id),
                        "author_id": str(message.author.id),
                        "created_at": created_at_kst
                    }

                    try:
                        affected = await asyncio.to_thread(upsert_notice, notice_data)
                        if affected > 0:
                            sync_count += 1
                    except Exception as e:
                        print(f"[Notice Sync Error] Msg ID {message.id}: {e}")

        await ctx.send(f"공지사항 동기화 완료: 총 {sync_count}건의 데이터가 적재/갱신되었습니다.")

    @commands.command(name="팁동기화")
    @commands.has_permissions(administrator=True)
    async def sync_tips_command(self, ctx: commands.Context):
        """빌드 및 길드 포럼의 전체 쓰레드를 DB에 동기화 (첨부파일 R2 업로드 포함)"""
        await ctx.send("팁 게시판(포럼) 전체 동기화를 시작합니다. 미디어 업로드에 시간이 소요될 수 있습니다.")

        try:
            build_forum_id = int(os.getenv('BUILD_FORUM_ID', 0))
            guild_forum_id = int(os.getenv('GUILD_FORUM_ID', 0))
        except ValueError:
            await ctx.send("환경 변수에 포럼 채널 ID가 올바르게 설정되지 않았습니다.")
            return

        forums_to_sync = [
            (build_forum_id, 'BUILD'),
            (guild_forum_id, 'GUILD')
        ]

        sync_count = 0
        youtube_regex = re.compile(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+)')

        async with aiohttp.ClientSession() as session:
            for forum_id, category in forums_to_sync:
                if not forum_id:
                    continue

                forum = self.bot.get_channel(forum_id) or await self.bot.fetch_channel(forum_id)
                if not forum or not isinstance(forum, discord.ForumChannel):
                    continue

                # 활성 쓰레드 및 보관된 쓰레드 병합 처리
                all_threads = forum.threads.copy()
                async for archived_thread in forum.archived_threads(limit=None):
                    all_threads.append(archived_thread)

                for thread in all_threads:
                    try:
                        # 실무 적용: fetch_message 단일 호출 폐기, history 제너레이터를 사용하여 쓰레드 내 모든 메시지 순회 및 병합
                        full_content_lines = []
                        uploaded_urls = []
                        youtube_urls = []

                        async for msg in thread.history(limit=None, oldest_first=True):
                            if msg.author.bot:
                                continue

                            if msg.author.id != thread.owner_id:
                                continue

                            if msg.clean_content.strip():
                                full_content_lines.append(msg.clean_content.strip())

                            if msg.attachments:
                                for att in msg.attachments:
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

                            youtube_urls.extend(youtube_regex.findall(msg.content))

                        if not full_content_lines and not uploaded_urls:
                            continue

                        tip_data = {
                            "category": category,
                            "title": thread.name,
                            "content": "\n\n".join(full_content_lines),
                            "image_urls": json.dumps(uploaded_urls),
                            "youtube_urls": json.dumps(list(set(youtube_urls))),
                            "discord_thread_id": str(thread.id),
                            "author_id": str(thread.owner_id)
                        }

                        affected = await asyncio.to_thread(upsert_tip, tip_data)
                        if affected > 0:
                            sync_count += 1

                    except Exception as e:
                        print(f"[Tip Sync Error] Thread ID {thread.id}: {e}")

                await ctx.send(f"팁 게시판 동기화 완료: 총 {sync_count}건의 쓰레드가 적재/갱신되었습니다.")

    @app_commands.command(name="testerror", description="[관리자 전용] 관제 채널 로깅 테스트")
    @app_commands.default_permissions(administrator=True)
    async def test_bot_error(self, interaction: discord.Interaction):
        """실무: 봇 관제 채널 에러 발송 테스트용 임시 명령어"""
        raise Exception("[Test] 디스코드 봇 관제 채널 모니터링 연동 테스트 에러입니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(BulkSyncCmd(bot))