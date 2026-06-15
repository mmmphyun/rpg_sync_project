import discord
import os
import asyncio
import mimetypes
from discord import app_commands
from discord.ext import commands
from src.database.jobs import update_job_single_column, update_job_illustrations
from src.database.skills import upsert_weapon_and_skill
from src.bot.utils.checks import has_staff_privilege
from src.database.cache import delete_cache
from src.bot.utils.s3_client import upload_to_r2, delete_from_r2

VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

def is_valid_image(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in VALID_IMAGE_EXTENSIONS

class JobGroupCog(commands.GroupCog, name="직업"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name="메타", description="직업의 메타 정보(사거리, 포지션)를 변경합니다.")
    @app_commands.guild_only()
    @has_staff_privilege()
    @app_commands.describe(
        job_name="변경할 직업명 (예: 다크메이지)",
        range_type="사거리 정보 (예: '근거리', '원거리', '근거리, 원거리')",
        position="포지션 정보 (예: '탱', '물리', '물리, 유틸')"
    )
    async def meta(self, interaction: discord.Interaction, job_name: str, range_type: str, position: str):
        await interaction.response.defer(thinking=True)
        try:
            affected_range = await asyncio.to_thread(update_job_single_column, job_name, "range", range_type)
            affected_position = await asyncio.to_thread(update_job_single_column, job_name, "position", position)

            if affected_range > 0 or affected_position > 0:
                await delete_cache("cache:jobs:all")
                await interaction.followup.send(f"[Success] `{job_name}`의 메타 정보(사거리: `{range_type}`, 포지션: `{position}`) 설정 완료")
            else:
                await interaction.followup.send(f"[Error] `{job_name}` 직업을 찾을 수 없습니다.")
        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '직업 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

    @app_commands.command(name="제한", description="직업의 제한 정보(제한 여부, 제한 조건)를 변경합니다.")
    @app_commands.guild_only()
    @has_staff_privilege()
    @app_commands.describe(
        job_name="변경할 직업명 (예: 다크메이지)",
        is_limit="제한 여부 (예: 'Y', 'N')",
        req_condition="제한 조건 (예: '2차 전직 완료')"
    )
    async def limit(self, interaction: discord.Interaction, job_name: str, is_limit: str, req_condition: str):
        await interaction.response.defer(thinking=True)
        try:
            affected_limit = await asyncio.to_thread(update_job_single_column, job_name, "is_limit", is_limit)
            affected_cond = await asyncio.to_thread(update_job_single_column, job_name, "req_condition", req_condition)

            if affected_limit > 0 or affected_cond > 0:
                await delete_cache("cache:jobs:all")
                await interaction.followup.send(f"[Success] `{job_name}`의 제한 정보(제한여부: `{is_limit}`, 제한조건: `{req_condition}`) 설정 완료")
            else:
                await interaction.followup.send(f"[Error] `{job_name}` 직업을 찾을 수 없습니다.")
        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '직업 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

    @app_commands.command(name="텍스트", description="직업의 일반 텍스트 속성을 변경합니다.")
    @app_commands.guild_only()
    @has_staff_privilege()
    @app_commands.describe(
        job_name="변경할 직업명 (예: 다크메이지)",
        column="변경할 속성 컬럼",
        value="새로 설정할 값"
    )
    @app_commands.choices(
        column=[
            app_commands.Choice(name="게이트", value="gate"),
            app_commands.Choice(name="계열", value="job_group"),
            app_commands.Choice(name="설명", value="description"),
            app_commands.Choice(name="자원타입", value="resource"),
            app_commands.Choice(name="타입", value="type")
        ]
    )
    async def text(self, interaction: discord.Interaction, job_name: str, column: app_commands.Choice[str], value: str):
        await interaction.response.defer(thinking=True)
        try:
            affected = await asyncio.to_thread(update_job_single_column, job_name, column.value, value)
            if affected > 0:
                await delete_cache("cache:jobs:all")
                await interaction.followup.send(f"[Success] `{job_name}`의 `{column.name}`({column.value}) 항목 업데이트 완료")
            else:
                await interaction.followup.send(f"[Error] `{job_name}` 직업을 찾을 수 없습니다.")
        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '직업 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

    @app_commands.command(name="프로필", description="직업의 프로필 이미지를 변경합니다.")
    @app_commands.guild_only()
    @has_staff_privilege()
    @app_commands.describe(
        job_name="변경할 직업명 (예: 다크메이지)",
        image="업로드할 이미지 첨부파일 (최대 15MB)"
    )
    async def profile(self, interaction: discord.Interaction, job_name: str, image: discord.Attachment):
        await interaction.response.defer(thinking=True)
        MAX_FILE_SIZE = 15 * 1024 * 1024
        r2_url = None
        try:
            if image.size > MAX_FILE_SIZE:
                await interaction.followup.send(f"[Error] 이미지는 최대 15MB까지만 업로드 가능합니다. (현재: {image.size / (1024 * 1024):.2f}MB)")
                return

            if not is_valid_image(image.filename):
                await interaction.followup.send(f"[Error] 지원하지 않는 파일 포맷입니다. (허용: {', '.join(VALID_IMAGE_EXTENSIONS)})")
                return

            file_bytes = await image.read()
            content_type, _ = mimetypes.guess_type(image.filename)

            r2_url = await asyncio.to_thread(
                upload_to_r2,
                file_bytes,
                image.filename,
                content_type or "image/png",
                "jobs_profile"
            )

            if not r2_url:
                await interaction.followup.send("[Error] R2 스토리지 업로드에 실패했습니다.")
                return

            affected = await asyncio.to_thread(update_job_single_column, job_name, "img", r2_url)
            if affected > 0:
                await delete_cache("cache:jobs:all")
                await interaction.followup.send(f"[Success] `{job_name}` 프로필 이미지 적용 완료\nURL: {r2_url}")
            else:
                raise ValueError(f"직업 '{job_name}'을 찾을 수 없습니다. R2 물리 이미지를 삭제하고 롤백합니다.")
        except Exception as e:
            if r2_url:
                try:
                    await asyncio.to_thread(delete_from_r2, r2_url)
                except Exception as del_err:
                    print(f"[Error] Failed to rollback R2 image {r2_url}: {del_err}")
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '직업 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

    @app_commands.command(name="일러스트", description="디스코드 메시지 링크에서 이미지를 가져와 직업의 일러스트로 등록합니다.")
    @app_commands.guild_only()
    @has_staff_privilege()
    @app_commands.describe(
        job_name="변경할 직업명 (예: 다크메이지)",
        message_url="일러스트 이미지들이 포함된 디스코드 메시지 링크"
    )
    async def illustration(self, interaction: discord.Interaction, job_name: str, message_url: str):
        await interaction.response.defer(thinking=True)
        MAX_FILE_SIZE = 15 * 1024 * 1024
        uploaded_urls = []
        try:
            if "discord.com/channels/" not in message_url:
                await interaction.followup.send("[Error] 일러스트 수정 시 유효한 디스코드 메시지 링크를 입력해야 합니다.")
                return

            parts = message_url.split("/")
            channel_id = int(parts[-2])
            message_id = int(parts[-1])

            target_channel = self.bot.get_channel(channel_id) or self.bot.get_thread(channel_id)
            if not target_channel:
                try:
                    target_channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    await interaction.followup.send("[Error] 대상 채널 또는 쓰레드에 봇이 접근할 수 없습니다.")
                    return

            try:
                target_message = await target_channel.fetch_message(message_id)
            except discord.NotFound:
                await interaction.followup.send("[Error] 대상 메시지를 찾을 수 없습니다.")
                return
            except discord.Forbidden:
                await interaction.followup.send("[Error] 메시지를 읽을 권한이 없습니다.")
                return

            valid_attachments = [att for att in target_message.attachments if
                                 is_valid_image(att.filename) and att.size <= MAX_FILE_SIZE]
            if not valid_attachments:
                await interaction.followup.send("[Error] 대상 메시지에 유효하거나 용량 제한(15MB)을 통과한 이미지 첨부파일이 존재하지 않습니다.")
                return

            target_attachments = valid_attachments[:4]

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
                await interaction.followup.send("[Error] 이미지 업로드 처리에 실패했습니다.")
                return

            affected = await asyncio.to_thread(update_job_illustrations, job_name, uploaded_urls)
            if affected > 0:
                await delete_cache("cache:jobs:all")
                await interaction.followup.send(f"[Success] `{job_name}` 일러스트({len(uploaded_urls)}장) 적용 완료")
            else:
                raise ValueError(f"직업 '{job_name}'을 찾을 수 없습니다. 업로드한 R2 이미지들을 일괄 롤백 삭제합니다.")
        except Exception as e:
            if uploaded_urls:
                try:
                    delete_tasks = [asyncio.to_thread(delete_from_r2, url) for url in uploaded_urls]
                    await asyncio.gather(*delete_tasks, return_exceptions=True)
                except Exception as del_err:
                    print(f"[Error] Failed to rollback R2 illustrations {uploaded_urls}: {del_err}")
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '직업 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

class SkillGroupCog(commands.GroupCog, name="스킬"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name="등록", description="직업의 무기 및 스킬 정보 등록/수정 (UPSERT)")
    @app_commands.guild_only()
    @has_staff_privilege()
    @app_commands.describe(
        job_name="대상 직업명 (예: 다크메이지)",
        weapon_type="무기 종류 (예: 지팡이)",
        weapon_name="무기명 (예: 초보자스태프)",
        command_key="커맨드 (예: 우클릭)",
        skill_name="스킬명 (예: 다크볼)",
        description="설명",
        cooldown="쿨타임 (예: 3초)",
        cost="코스트 (예: 10)",
        coefficient="계수 (예: 지력 * 1.5)",
        damage_type="피해 타입 (예: 마법)",
        is_mobility="이동기 여부",
        form_name="폼 이름 (기본값: '기본')"
    )
    @app_commands.choices(
        is_mobility=[
            app_commands.Choice(name="Y", value="Y"),
            app_commands.Choice(name="N", value="N")
        ]
    )
    async def register(
        self,
        interaction: discord.Interaction,
        job_name: str,
        weapon_type: str,
        weapon_name: str,
        command_key: str,
        skill_name: str,
        description: str,
        cooldown: str,
        cost: str,
        coefficient: str,
        damage_type: str,
        is_mobility: app_commands.Choice[str],
        form_name: str = "기본"
    ):
        await interaction.response.defer(thinking=True)
        try:
            if len(weapon_name) > 100:
                await interaction.followup.send("[Error] 무기명은 100자를 초과할 수 없습니다.")
                return
            if len(command_key) > 50:
                await interaction.followup.send("[Error] 커맨드는 50자를 초과할 수 없습니다.")
                return
            if len(skill_name) > 100:
                await interaction.followup.send("[Error] 스킬명은 100자를 초과할 수 없습니다.")
                return

            coefficient_combined = f"{coefficient} ({damage_type})"

            success = await asyncio.to_thread(
                upsert_weapon_and_skill,
                job_name, weapon_type, weapon_name, command_key, skill_name,
                description, cooldown, cost, coefficient_combined, is_mobility.value, form_name
            )

            if success:
                await delete_cache("cache:jobs:all")
                await interaction.followup.send(f"[Success] `{job_name}` - `{weapon_name}({weapon_type})`의 `{skill_name}` 스킬 정보 갱신 완료")
            else:
                await interaction.followup.send(f"[Error] `{job_name}` 직업을 찾을 수 없거나 스킬 등록에 실패했습니다.")
        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '스킬 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(JobGroupCog(bot))
    await bot.add_cog(SkillGroupCog(bot))