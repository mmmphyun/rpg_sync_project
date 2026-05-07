import discord
import os
import asyncio
import mimetypes
from discord.ext import commands
from src.bot.cogs.core.base_cog import BaseCog
from src.database.jobs import update_job_single_column, update_job_illustrations
from src.bot.utils.s3_client import upload_to_r2
from src.database.cache import delete_cache
from src.database.skills import upsert_weapon_and_skill

VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

def is_valid_image(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in VALID_IMAGE_EXTENSIONS

class JobCmd(BaseCog):

    @commands.command(name="직업수정")
    @commands.has_permissions(administrator=True)
    async def update_job_command(self, ctx: commands.Context, job_name: str, column: str, *, value: str | None = None):
        """
        Usage: !직업수정 <직업명> <항목> [<값/메시지ID>]
        """
        try:
            if column == "img":
                if not ctx.message.attachments:
                    await ctx.send("[Error] img 속성 수정 시 프로필 이미지를 첨부해야 합니다.")
                    return

                attachment = ctx.message.attachments[0]
                if not is_valid_image(attachment.filename):
                    await ctx.send(f"[Error] 지원하지 않는 파일 포맷입니다. (허용: {', '.join(VALID_IMAGE_EXTENSIONS)})")
                    return

                file_bytes = await attachment.read()
                content_type, _ = mimetypes.guess_type(attachment.filename)

                r2_url = await asyncio.to_thread(
                    upload_to_r2,
                    file_bytes,
                    attachment.filename,
                    content_type or "image/png",
                    "jobs_profile"
                )

                if not r2_url:
                    await ctx.send("[Error] R2 스토리지 업로드에 실패했습니다.")
                    return

                affected = update_job_single_column(job_name, column, r2_url)
                if affected > 0:
                    await delete_cache("cache:jobs:all")
                    await ctx.send(f"[Success] `{job_name}` 프로필 이미지 적용 완료\nURL: {r2_url}")
                else:
                    await ctx.send(f"[Error] `{job_name}` 직업을 찾을 수 없습니다.")
                return


            elif column == "illustration":
                if not value or "discord.com/channels/" not in value:
                    await ctx.send("[Error] illustration 수정 시 유효한 디스코드 메시지 링크를 입력해야 합니다.")
                    return

                try:
                    parts = value.split("/")
                    channel_id = int(parts[-2])
                    message_id = int(parts[-1])

                    target_channel = ctx.guild.get_channel(channel_id) or ctx.guild.get_thread(channel_id)
                    if not target_channel:
                        await ctx.send("[Error] 대상 채널 또는 쓰레드에 봇이 접근할 수 없습니다.")
                        return

                    target_message = await target_channel.fetch_message(message_id)
                except (ValueError, IndexError, discord.NotFound, discord.Forbidden):
                    await ctx.send("[Error] 메시지 링크 검증 실패 또는 대상 메시지를 읽을 수 없습니다.")
                    return

                valid_attachments = [att for att in target_message.attachments if is_valid_image(att.filename)]
                if not valid_attachments:
                    await ctx.send("[Error] 대상 메시지에 유효한 이미지 첨부파일이 존재하지 않습니다.")
                    return

                target_attachments = valid_attachments[:4]
                uploaded_urls = []

                for att in target_attachments:
                    file_bytes = await att.read()
                    content_type, _ = mimetypes.guess_type(att.filename)
                    url = await asyncio.to_thread(
                        upload_to_r2,
                        file_bytes,
                        att.filename,
                        content_type or "image/png",
                        "jobs_illustration"
                    )
                    if url:
                        uploaded_urls.append(url)

                if not uploaded_urls:
                    await ctx.send("[Error] 이미지 업로드 처리에 실패했습니다.")
                    return

                affected = update_job_illustrations(job_name, uploaded_urls)
                if affected > 0:
                    await delete_cache("cache:jobs:all")
                    await ctx.send(f"[Success] `{job_name}` 일러스트({len(uploaded_urls)}장) 적용 완료")
                else:
                    await ctx.send(f"[Error] `{job_name}` 직업을 찾을 수 없습니다.")
                return

            if value is None:
                await ctx.send("[Error] 텍스트 항목 수정 시 value 값을 입력해야 합니다.")
                return

            affected = update_job_single_column(job_name, column, value)
            if affected > 0:
                await delete_cache("cache:jobs:all")
                await ctx.send(f"[Success] `{job_name}`의 `{column}` 항목 업데이트 완료")
            else:
                await ctx.send(f"[Error] `{job_name}` 직업을 찾을 수 없습니다.")

        except ValueError:
            await ctx.send("[Error] 지원하지 않는 항목입니다. (지원: range, position, resource, img, illustration 등)")
        except Exception as e:
            await ctx.send(f"[Error] 처리 중 예외 발생: {str(e)}")

    @update_job_command.error
    async def update_job_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            error_msg = (
                "[Error] 필수 입력값이 누락되었습니다.\n"
                "사용법: `!직업수정 <직업명> <항목> [<값/메시지ID>]`\n"
                "* 텍스트 항목 예시: `!직업수정 다크메이지 range 원거리`\n"
                "* 이미지 항목 예시: `!직업수정 다크메이지 img` (이미지 파일 첨부 필수)"
            )
            await ctx.send(error_msg)
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("[Error] 명령어 실행 권한이 없습니다.")

    @commands.command(name="스킬등록")
    @commands.has_permissions(administrator=True)
    async def register_skill_command(self, ctx: commands.Context, job_name: str, weapon_type: str, weapon_name: str,
                                     command_key: str, skill_name: str, *, details: str):
        """
        직업 무기 및 스킬 정보 등록/수정 (UPSERT)
        """
        try:
            parts = [p.strip() for p in details.split('|')]
            if len(parts) < 6:
                await ctx.send("[Error] 상세 정보 포맷 오류. (형식: 설명|쿨타임|코스트|계수|피해타입|이동기|[폼이름])")
                return

            description = parts[0]
            cooldown = parts[1]
            cost_value = parts[2]
            coefficient_combined = f"{parts[3]} ({parts[4]})"
            is_mobility = parts[5].upper()

            form_name = parts[6] if len(parts) > 6 and parts[6] else "기본"

            if len(weapon_name) > 100:
                raise ValueError("무기명은 100자를 초과할 수 없습니다.")
            if len(command_key) > 50:
                raise ValueError("커맨드는 50자를 초과할 수 없습니다.")
            if len(skill_name) > 100:
                raise ValueError("스킬명은 100자를 초과할 수 없습니다.")
            if is_mobility not in ('Y', 'N'):
                raise ValueError("이동기 여부는 'Y' 또는 'N'으로만 입력해야 합니다.")

            success = await asyncio.to_thread(
                upsert_weapon_and_skill,
                job_name, weapon_type, weapon_name, command_key, skill_name,
                description, cooldown, cost_value, coefficient_combined, is_mobility, form_name
            )

            if success:
                await delete_cache("cache:jobs:all")
                await ctx.send(f"[Success] `{job_name}` - `{weapon_name}({weapon_type})`의 `{skill_name}` 스킬 정보 갱신 완료")

        except ValueError as ve:
            await ctx.send(f"[Error] {str(ve)}")
        except Exception as e:
            await ctx.send(f"[Error] 처리 중 예외 발생: {str(e)}")

    @register_skill_command.error
    async def register_skill_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            error_msg = (
                "[Error] 필수 입력값이 누락되었습니다.\n"
                "사용법: `!스킬등록 <직업명> <무기종류> <무기명> <커맨드> <스킬명> <설명|쿨타임|코스트|계수|피해타입|이동기Y/N|[폼이름]>`\n"
                "예시: `!스킬등록 다크메이지 지팡이 초보자스태프 우클릭 다크볼 적에게 암흑구를 발사|3초|10|지력 * 1.5|마법|N|각성폼`"
            )
            await ctx.send(error_msg)
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("[Error] 명령어 실행 권한이 없습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(JobCmd(bot))