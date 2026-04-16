import os
import discord
from discord.ext import commands
from src.database.queries import update_job_single_column, update_job_illustrations
from src.database.connection import sync_users_to_db, sync_jobs_to_db, sync_job_patch_to_db
from src.bot.utils.text_parser import parse_job_descriptions, parse_job_patches, parse_job_illustration


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
    """서버 내 전체 유저의 ID, 닉네임, 역할을 DB와 동기화합니다."""
    await ctx.send("유저 동기화를 시작합니다. (서버 크기에 따라 시간이 소요될 수 있습니다)")

    users_data = []
    for member in ctx.guild.members:
        if not member.bot:
            # 최상위 역할명 추출
            role_name = member.top_role.name if member.top_role else "유저"
            users_data.append({
                "discord_id": str(member.id),
                "nickname": member.display_name,
                "server_role": role_name
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
                    sync_job_patch_to_db(parsed_data)
                    patch_count += 1

    # 3. 일러스트 동기화 (JOBS 테이블 PHOTO 업데이트)
    illust_channel = self.bot.get_channel(illust_thread_id) or await self.bot.fetch_channel(illust_thread_id)
    illust_count = 0
    if illust_channel:
        async for message in illust_channel.history(limit=None, oldest_first=True):
            if not message.author.bot and message.attachments:
                job_name = parse_job_illustration(message.content)
                if job_name:
                    image_urls = [att.url for att in message.attachments[:4]]
                    update_job_illustrations(job_name, image_urls)
                    illust_count += 1

    await ctx.send(f"일괄 데이터 동기화 완료\n- 파싱된 직업: {desc_count}건\n- 적재된 패치노트: {patch_count}건\n- 연결된 일러스트: {illust_count}건")


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCmd(bot))