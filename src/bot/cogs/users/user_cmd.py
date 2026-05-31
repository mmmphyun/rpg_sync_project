import discord
import os
import asyncio
import re
import json
from discord import app_commands
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.database.auth import register_verified_user, update_user_minecraft_info
from src.database.cache import redis_client
from src.bot.cogs.auth.onboarding_modal import format_uuid
from src.bot.utils.checks import has_staff_privilege, StaffPermissionRequired

class UserCmd(BaseCog):
    """스태프용 인증 복구 및 예외 처리 명령어 Cog"""

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """이 Cog 내부 슬래시 커맨드 예외 처리 전용 핸들러 (스태프 권한 에러 가로채기)"""
        if isinstance(error, app_commands.errors.CommandInvokeError):
            error = error.original

        if isinstance(error, StaffPermissionRequired):
            # 스태프 권한 오류 시 안전하게 에페메럴 피드백 제공 (관제 채널 전송 방지)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ **권한 없음**\n{error}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ **권한 없음**\n{error}", ephemeral=True)
        else:
            # 기타 예외는 전역 관제탑(main.py)이 감지하도록 위로 전파
            raise error

    @app_commands.command(name="초기화", description="해당 유저의 성인인증 오입력 잠금을 해제합니다. (스태프 전용)")
    @app_commands.describe(target="실패 횟수를 초기화할 대상 유저")
    @has_staff_privilege() # 스태프 권한 체크 전역 데코레이터 적용
    async def reset_verification_fail(self, interaction: discord.Interaction, target: discord.User):
        await interaction.response.defer(ephemeral=True)
        user_id = str(target.id)
        fail_key = f"rpgsync:fail:{user_id}"

        try:
            # Redis에서 해당 유저의 실패 횟수 키 삭제
            await redis_client.delete(fail_key)
            
            await interaction.followup.send(
                f"✅ **초기화 완료**\n"
                f"{target.mention} ({target.display_name}) 유저의 성인인증 실패 횟수를 성공적으로 초기화했습니다. "
                f"이제 모달을 통한 재인증 시도가 가능합니다.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[Staff Command Error] /인증초기화 실패: {e}")
            await interaction.followup.send("⚠️ Redis 캐시 초기화 도중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)

    @app_commands.command(name="수동인증", description="Mojang API 장애 시 유저의 정보를 수동으로 DB 및 캐시에 강제 등록합니다. (스태프 전용)")
    @app_commands.describe(
        target="등록할 대상 유저",
        kr_name="서버 및 DB에 등록할 한글 닉네임 (1~3자)",
        mc_name="정확한 마인크래프트 정품 닉네임",
        mc_uuid="마인크래프트 UUID (대소문자/하이픈 무관)"
    )
    @has_staff_privilege() # 스태프 권한 체크 전역 데코레이터 적용
    async def manual_verification_register(
        self,
        interaction: discord.Interaction,
        target: discord.User,
        kr_name: str,
        mc_name: str,
        mc_uuid: str
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = str(target.id)

        # 1. 한글 닉네임 유효성 검사 및 정규화
        clean_kr = kr_name.strip().replace(" ", "")
        if not re.match("^[가-힣0-9]{1,3}$", clean_kr):
            await interaction.followup.send(
                "❌ **한글 닉네임 정규식 불일치**\n"
                "한글 닉네임은 한글과 숫자로 구성된 1~3자여야 합니다.",
                ephemeral=True
            )
            return

        if len(clean_kr) == 2:
            final_kr = f"{clean_kr[0]} {clean_kr[1]}"
        else:
            final_kr = clean_kr

        # 2. UUID 표준 규격 정규화 변환 (하이픈 4개 포함 36자리 소문자)
        clean_uuid = mc_uuid.strip().lower().replace("-", "")
        if len(clean_uuid) != 32:
            await interaction.followup.send(
                "❌ **UUID 형식 올바르지 않음**\n"
                "제출된 UUID가 32자리 원시 문자열이 아닙니다. 정확한 UUID를 입력해주세요.",
                ephemeral=True
            )
            return
        
        final_uuid = format_uuid(clean_uuid)

        try:
            # 3. DB 강제 업서트 (바이패스는 기본 False)
            guild_member = interaction.guild.get_member(target.id) if interaction.guild else None
            server_role = guild_member.top_role.name if guild_member and guild_member.top_role else "유저"
            
            db_success = await asyncio.to_thread(
                register_verified_user,
                user_id,
                final_kr,
                server_role,
                final_uuid,
                mc_name,
                False
            )

            # UNIQUE 제약조건 위반 에러 가로채기
            if db_success == "UUID_DUPLICATE":
                await interaction.followup.send(
                    "❌ **수동 등록 실패**\n입력하신 마인크래프트 UUID는 **이미 다른 유저가 연동하여 사용 중**입니다.",
                    ephemeral=True
                )
                return
            elif db_success == "MC_NAME_DUPLICATE":
                await interaction.followup.send(
                    "❌ **수동 등록 실패**\n입력하신 마인크래프트 닉네임은 **이미 다른 유저가 연동하여 사용 중**입니다.",
                    ephemeral=True
                )
                return
            elif not db_success:
                raise Exception("DB register_verified_user 실행 실패")

            # 4. Redis 디코 ID - 마크 UUID/닉네임 맵핑 영구 캐싱 (음성 감지 DB I/O 0화 목적 - JSON 구조)
            cache_data = {
                "uuid": final_uuid,
                "username": mc_name
            }
            await redis_client.set(f"rpgsync:user_mc:{user_id}", json.dumps(cache_data, ensure_ascii=False))

            # 5. Redis 오입력 실패 세션 삭제
            await redis_client.delete(f"rpgsync:fail:{user_id}")

            # 6. 디스코드 멤버 서버 별명 강제 변경 (실제 뉴비 닉네임 양식 "한글이름ㅣ백수" 준수)
            if guild_member:
                new_nick = f"{final_kr}ㅣ백수"
                if len(new_nick) > 32:
                    new_nick = new_nick[:32]
                try:
                    await guild_member.edit(nick=new_nick, reason="스태프에 의한 수동 성인인증 등록 별명 변경")
                except discord.Forbidden:
                    pass

            await interaction.followup.send(
                f"✅ **수동 인증 등록 성공**\n"
                f"대상: {target.mention}\n"
                f"한글 닉네임: `{final_kr}`\n"
                f"마크 닉네임: `{mc_name}`\n"
                f"등록 UUID: `{final_uuid}` (표준 규격 변환 완료)\n\n"
                f"- DB 업서트, Redis JSON 맵핑 캐싱, 실패 세션 초기화가 완료되었습니다.",
                ephemeral=True
            )

        except Exception as e:
            print(f"[Staff Command Error] /인증수동등록 오류: {e}")
            await interaction.followup.send("⚠️ 데이터베이스 연동 및 캐시 적재 과정 중 시스템 장애가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="연동", description="기존 디코 별명을 바꾸지 않고, 오직 마인크래프트 UUID와 닉네임만 업데이트합니다. (스태프 전용)")
    @app_commands.describe(
        target="연동할 대상 유저 (멘션)",
        mc_name="정확한 마인크래프트 정품 닉네임"
    )
    @has_staff_privilege()
    async def link_user_uuid(
        self,
        interaction: discord.Interaction,
        target: discord.User,
        mc_name: str
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = str(target.id)

        # 1. Mojang API를 이용해 정품 계정 및 UUID 비동기 검증
        uuid_36 = None
        real_mc_name = mc_name
        
        bot_session = interaction.client.session if hasattr(interaction.client, "session") and interaction.client.session else None
        
        try:
            import aiohttp
            if bot_session and not bot_session.closed:
                async with bot_session.get(f"https://api.mojang.com/users/profiles/minecraft/{mc_name}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_uuid = data.get("id")
                        real_mc_name = data.get("name", mc_name)
                        if raw_uuid:
                            uuid_36 = format_uuid(raw_uuid)
                    elif response.status == 429:
                        await interaction.followup.send("⚠️ 현재 Mojang API 서버 요청이 혼잡합니다. 잠시 후 시도해주세요.", ephemeral=True)
                        return
            else:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as fallback_session:
                    async with fallback_session.get(f"https://api.mojang.com/users/profiles/minecraft/{mc_name}") as response:
                        if response.status == 200:
                            data = await response.json()
                            raw_uuid = data.get("id")
                            real_mc_name = data.get("name", mc_name)
                            if raw_uuid:
                                uuid_36 = format_uuid(raw_uuid)
                        elif response.status == 429:
                            await interaction.followup.send("⚠️ 현재 Mojang API 서버 요청이 혼잡합니다. 잠시 후 시도해주세요.", ephemeral=True)
                            return
        except Exception as api_err:
            print(f"[Staff Command Error] /uuid연동 Mojang API 오류: {api_err}")
            await interaction.followup.send("⚠️ 마인크래프트 계정 조회 중 시스템 장애가 발생했습니다.", ephemeral=True)
            return

        if not uuid_36:
            await interaction.followup.send("❌ 존재하지 않는 마인크래프트 정품 계정입니다. 스펠링을 다시 확인해주세요.", ephemeral=True)
            return

        try:
            # 2. DB 업데이트 진행 (기존 닉네임/별명 절대 미터치)
            db_success = await asyncio.to_thread(
                update_user_minecraft_info,
                user_id,
                uuid_36,
                real_mc_name
            )

            # UNIQUE 제약조건 위반 에러 가로채기
            if db_success == "UUID_DUPLICATE":
                await interaction.followup.send(
                    "❌ **연동 실패**\n조회된 마인크래프트 UUID는 **이미 다른 유저가 연동하여 사용 중**입니다.",
                    ephemeral=True
                )
                return
            elif db_success == "MC_NAME_DUPLICATE":
                await interaction.followup.send(
                    "❌ **연동 실패**\n조회된 마인크래프트 닉네임은 **이미 다른 유저가 연동하여 사용 중**입니다.",
                    ephemeral=True
                )
                return
            elif not db_success:
                # 만약 DB에 유저가 아예 존재하지 않는 경우
                await interaction.followup.send(
                    "❌ **연동 실패**\n해당 디스코드 유저가 DB에 존재하지 않습니다. 먼저 서버 성인인증 절차를 밟았는지 확인해주세요.",
                    ephemeral=True
                )
                return

            # 3. Redis 디코 ID - 마크 UUID/닉네임 맵핑 영구 캐싱 (JSON 구조)
            cache_data = {
                "uuid": uuid_36,
                "username": real_mc_name
            }
            await redis_client.set(f"rpgsync:user_mc:{user_id}", json.dumps(cache_data, ensure_ascii=False))

            await interaction.followup.send(
                f"✅ **마크 UUID 연동 성공**\n"
                f"대상: {target.mention}\n"
                f"마크 닉네임: `{real_mc_name}`\n"
                f"연동 UUID: `{uuid_36}` (표준 규격 변환 완료)\n\n"
                f"- 디코 별명(닉네임)은 일절 변경되지 않았으며, 오직 DB/Redis 마크 연동 데이터만 갱신 완료되었습니다.",
                ephemeral=True
            )

        except Exception as e:
            print(f"[Staff Command Error] /uuid연동 오류: {e}")
            await interaction.followup.send("⚠️ 데이터베이스 연동 및 캐시 적재 과정 중 시스템 장애가 발생했습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(UserCmd(bot))
