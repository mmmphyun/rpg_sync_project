import discord
from discord import app_commands
from discord.ext import commands

from datetime import timedelta

from src.database.queries import update_job_single_column, update_job_illustrations, batch_update_profile_images
from src.database.connection import sync_users_to_db, sync_jobs_to_db, sync_job_patch_to_db
from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration
from src.bot.utils.s3_client import upload_to_r2
from src.database.queries import check_user_exists, create_magic_token

import os
import re
import asyncio
import aiohttp

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
        discord_id = str(interaction.user.id)

        # 1. DB에 유저가 존재하는지 확인
        if not check_user_exists(discord_id):
            # 2. 존재하지 않는다면 해당 유저 정보만 단건 동기화 진행
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

            # 단건 동기화 실행 (sync_users_to_db는 리스트를 받도록 설계됨)
            sync_result = sync_users_to_db(user_data)
            if sync_result == 0:
                await interaction.response.send_message("유저 정보를 서버에 등록하는 중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)
                return

        # 3. 토큰 발급 및 메시지 전송
        try:
            token = create_magic_token(discord_id)
            # 개발 환경 및 운영 환경 도메인 처리
            domain = os.getenv("WEB_DOMAIN", "http://localhost:8000")
            login_url = f"{domain}/api/v1/auth/verify?token={token}"

            await interaction.response.send_message(
                f"✅ **인증 링크가 발급되었습니다.**\n"
                f"5분 안에 아래 링크를 클릭하여 접속하세요. 이 링크는 본인만 볼 수 있으며 1회만 사용 가능합니다.\n\n"
                f"🔗 [Fossile Wiki 로그인]({login_url})",
                ephemeral=True
            )
        except Exception as e:
            print(f"토큰 발급 에러: {e}")
            await interaction.response.send_message("인증 링크 발급 중 시스템 오류가 발생했습니다.", ephemeral=True)

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
        await ctx.send("유저 동기화를 시작합니다. (서버 크기에 따라 시간이 소요될 수 있습니다)")

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
        await ctx.send("게시글 일괄 데이터 동기화를 시작합니다. 외래키 무결성을 위해 직업설명 -> 패치노트 -> 일러스트 순으로 진행됩니다.")

        target_ids_str = os.getenv('TARGET_CHANNEL_IDS', '')
        id_list = [int(c_id.strip().replace('"', '').replace("'", ""))
                   for c_id in target_ids_str.split(',') if c_id.strip().isdigit()]

        if len(id_list) < 3:
            await ctx.send("환경 변수(TARGET_CHANNEL_IDS)에 3개의 채널 ID가 모두 설정되지 않아 중단합니다.")
            return

        patch_channel_id, desc_thread_id, illust_thread_id = id_list[0], id_list[1], id_list[2]

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
                    parsed_data = parse_job_patches(message.content)
                    if parsed_data:
                        # UTC 기준인 message.created_at에 9시간을 더해 KST(한국 시간)로 변환
                        kst_time = message.created_at + timedelta(hours=9)
                        patch_date_str = kst_time.strftime('%Y-%m-%d')

                        # 파서가 단일 딕셔너리 또는 리스트를 반환할 경우 모두 대응
                        if isinstance(parsed_data, list):
                            for pd in parsed_data:
                                pd['patch_date'] = patch_date_str
                                sync_job_patch_to_db(pd)
                                patch_count += 1
                        else:
                            parsed_data['patch_date'] = patch_date_str
                            sync_job_patch_to_db(parsed_data)
                            patch_count += 1

                # 3. 일러스트 동기화 (JOBS 테이블 PHOTO 업데이트)
                illust_channel = self.bot.get_channel(illust_thread_id) or await self.bot.fetch_channel(
                    illust_thread_id)
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