import discord
import os
import re
import asyncio
import aiohttp
import json

from discord import app_commands
from discord.ext import commands

from datetime import timedelta, datetime, timezone

from src.database.queries import update_job_single_column, update_job_illustrations, batch_update_profile_images, upsert_notice
from src.database.connection import sync_users_to_db, sync_jobs_to_db, sync_job_patch_to_db
from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration
from src.bot.utils.s3_client import upload_to_r2
from src.database.queries import check_user_exists, create_magic_token

class SyncCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 이 명령어를 실행할 관리자 권한이 없습니다.")
        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send(f"❌ 실행 중 오류가 발생했습니다: {error.original}")
        else:
            print(f"[명령어 에러] {error}")

    @app_commands.command(name="위키", description="위키 로그인을 위한 1회용 인증 링크를 발급합니다.")
    async def forum_login(self, interaction: discord.Interaction):
        # 1. 3초 타임아웃 방지를 위해 응답 지연 (ephemeral 속성 유지)
        await interaction.response.defer(ephemeral=True)

        discord_id = str(interaction.user.id)

        try:
            # 2. 동기 DB 작업들을 이벤트 루프 블로킹 방지를 위해 스레드 분리 실행
            user_exists = await asyncio.to_thread(check_user_exists, discord_id)

            if not user_exists:
                role_name = interaction.user.top_role.name if interaction.user.top_role else "유저"
                display_name = interaction.user.display_name
                parts = [p.strip() for p in re.split(r'[ㅣ]', display_name)]

                job_name = None
                actual_nickname = display_name
                if len(parts) >= 2:
                    actual_nickname = parts[-2]
                    job_name = parts[-1].replace(" ", "")
                elif len(parts) == 1:
                    actual_nickname = parts[0]

                if job_name and not job_name.strip():
                    job_name = None

                user_data = [{
                    "discord_id": discord_id,
                    "nickname": actual_nickname,
                    "server_role": role_name,
                    "job_name": job_name
                }]

                sync_result = await asyncio.to_thread(sync_users_to_db, user_data)
                if sync_result == 0:
                    # defer() 호출 이후에는 response가 아닌 followup.send()를 사용해야 함
                    await interaction.followup.send("유저 정보를 서버에 등록하는 중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)
                    return

            # 3. 토큰 발급 및 메시지 전송
            token = await asyncio.to_thread(create_magic_token, discord_id)
            domain = os.getenv("WEB_DOMAIN", "https://fossile-wiki.cloud")
            login_url = f"{domain}/api/v1/auth/login?token={token}"

            await interaction.followup.send(
                f"**인증 링크가 발급되었습니다.**\n"
                f"5분 안에 아래 링크를 클릭하여 접속하세요. 이 링크는 본인만 볼 수 있으며 1회만 사용 가능합니다.\n\n"
                f"[Fossile Wiki 로그인]({login_url})",
                ephemeral=True
            )
        except Exception as e:
            print(f"토큰 발급 에러: {e}")
            await interaction.followup.send("인증 링크 발급 중 시스템 오류가 발생했습니다.", ephemeral=True)

    @commands.command(name="직업수정")
    @commands.has_permissions(administrator=True)
    async def update_job_command(self, ctx: commands.Context, job_name: str, column: str, *, value: str):
        """
        Usage: !직업수정 <직업명> <항목> <값>
        Example: !직업수정 다크메이지 img https://example.com/img.png
        """
        try:
            affected = update_job_single_column(job_name, column, value)

            if affected > 0:
                await ctx.send(f"✅ `{job_name}`의 `{column}` 항목이 성공적으로 업데이트되었습니다.")
            else:
                await ctx.send(f"⚠️ `{job_name}` 직업을 찾을 수 없습니다.")

        except ValueError as ve:
            await ctx.send(f"❌ 지원하지 않는 항목입니다. 지원 항목: range, position, resource, img, photo1~4")
        except Exception as e:
            await ctx.send(f"❌ 데이터베이스 처리 중 오류가 발생했습니다: {str(e)}")

    @update_job_command.error
    async def update_job_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("사용법: `!직업수정 <직업명> <항목> <값>`\n예시: `!직업수정 다크메이지 range 원거리`")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("명령어 실행 권한이 없습니다.")

    @commands.command(name="유저동기화")
    @commands.has_permissions(administrator=True)
    async def sync_users_command(self, ctx: commands.Context):
        """서버 내 전체 유저의 ID, 닉네임, 역할 및 직업을 DB와 동기화합니다."""
        await ctx.send("유저 동기화를 시작합니다.")

        users_data = []
        for member in ctx.guild.members:
            if not member.bot:
                role_name = member.top_role.name if member.top_role else "유저"

                # 닉네임 파싱
                display_name = member.display_name
                parts = [p.strip() for p in re.split(r'[ㅣ]', display_name)]

                job_name = None
                actual_nickname = display_name
                if len(parts) >= 2:
                    actual_nickname = parts[-2]
                    job_name = parts[-1].replace(" ", "")
                elif len(parts) == 1:
                    actual_nickname = parts[0]

                if job_name and not job_name.strip():
                    job_name = None

                users_data.append({
                    "discord_id": str(member.id),
                    "nickname": actual_nickname,
                    "server_role": role_name,
                    "job_name": job_name
                })

        success_count = sync_users_to_db(users_data)
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
                        sync_jobs_to_db(parsed_data)
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
                        sync_job_patch_to_db(parsed_data)
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
                                update_job_illustrations(job_name, uploaded_urls)
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

                    notice_data = {
                        "type": "notice",
                        "tag": "일반 공지",
                        "content": message.content,
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

    @commands.command(name="이미지일괄적용")
    @commands.has_permissions(administrator=True)
    async def batch_sync_images_command(self, ctx: commands.Context):
        """Process batch update for local profile images in public/images."""
        img_dir = "public/images"
        if not os.path.exists(img_dir):
            await ctx.send("[Error] public/images 폴더를 찾을 수 없습니다.")
            return

        image_data = {}
        valid_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

        for filename in os.listdir(img_dir):
            name, ext = os.path.splitext(filename)
            if ext.lower() in valid_exts:
                image_data[name] = f"/images/{filename}"

        if not image_data:
            await ctx.send("[System] 적용할 이미지 파일이 없습니다.")
            return

        success_count = batch_update_profile_images(image_data)
        await ctx.send(f"[Success] 프로필 이미지 일괄 적용 완료 (적용 건수: {success_count}건)")


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCmd(bot))