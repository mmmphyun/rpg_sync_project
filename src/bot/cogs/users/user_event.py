import discord
import re
import asyncio
import os
import json
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.database.connection import sync_users_to_db
from src.database.auth import delete_user_from_db, get_user_minecraft_info
from src.database.cache import delete_cache, redis_client, publish_message
from src.bot.utils.text_parser import parse_user_nickname

class UserEvent(BaseCog):

    async def send_staff_error_log(self, guild: discord.Guild, member: discord.Member, error_type: str, detail: str):
        """스태프 전용 채널로 실시간 닉네임 동기화 에러 로그를 전송합니다."""
        staff_channel_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
        if not staff_channel_id:
            return
        
        channel = guild.get_channel(staff_channel_id)
        if not channel:
            try:
                channel = await guild.fetch_channel(staff_channel_id)
            except Exception:
                return

        if channel:
            embed = discord.Embed(
                title="⚠️ 유저 닉네임 동기화 실패 감지",
                color=discord.Color.red(),
                description=f"유저가 변경한 닉네임이 시스템 설정에 부합하지 않거나 직업 충돌이 발생했습니다."
            )
            embed.add_field(name="대상 유저", value=f"{member.display_name} ({member.name})", inline=True)
            embed.add_field(name="디스코드 ID", value=str(member.id), inline=True)
            embed.add_field(name="시도한 별명", value=f"`{member.display_name}`", inline=False)
            embed.add_field(name="오류 유형", value=f"**{error_type}**", inline=True)
            embed.add_field(name="상세 내용", value=detail, inline=False)
            
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """유저 닉네임 변경 감지 및 단건 동기화"""
        if before.bot:
            return

        if before.display_name == after.display_name:
            return

        formats = getattr(self.bot, "nickname_formats", None)
        
        # 1. 양식 불일치 유저 감지 및 예외 로그 전송
        if formats:
            has_valid_format = False
            cleaned_name = re.sub(r'[\(\[\{]?(?:STF|stf)[\)\]\}]?|🌈', '', after.display_name)
            for fmt in formats:
                delim = fmt.get("delimiter", "ㅣ")
                temp_parts = [p.strip() for p in re.split(re.escape(delim), cleaned_name) if p.strip()]
                if len(temp_parts) == fmt.get("part_count"):
                    has_valid_format = True
                    break
            
            if not has_valid_format:
                print(f"[Sync Alert] {after.display_name} - No matching layout part count. Skiped.")
                detail = (
                    f"현재 별명 구조가 설정된 어떤 닉네임 양식과도 일치하지 않습니다.\n"
                    f"등록된 구분자 양식을 충족하도록 별명을 수정해주세요."
                )
                await self.send_staff_error_log(after.guild, after, "양식 불일치 (Format Mismatch)", detail)
                return

        try:
            # 공통 파서 유틸리티를 사용하여 닉네임 파싱 및 정제
            parsed = parse_user_nickname(after.display_name, formats)
            actual_nickname = parsed["nickname"]
            server_role = parsed["server_role"]
            job_name = parsed["job_name"]

            user_data = {
                "discord_id": str(after.id),
                "nickname": actual_nickname,
                "server_role": server_role,
                "job_name": job_name
            }

            # 2. DB 동기화 실행 (복수 직업 충돌 가능성 대응)
            result = await asyncio.to_thread(sync_users_to_db, [user_data])
            
            # 단건 전송이었으므로 실패한 유저 리스트에 포함되어 있는지 확인
            if result.get("failed_users"):
                fu = result["failed_users"][0]
                print(f"[Sync Alert] Job collision for {after.display_name}: {fu['reason']}")
                await self.send_staff_error_log(
                    after.guild, 
                    after, 
                    "직업명 중복 충돌 (Job Collision)", 
                    f"입력값 중 직업명이 여러 전역 직업과 중복 검색됩니다.\n**사유**: {fu['reason']}"
                )
                return

            if result.get("success_count", 0) > 0:
                await delete_cache("cache:jobs:all")
                print(f"[Info] 유저 정보 변경 동기화 완료: {before.display_name} -> {after.display_name} ({after.id})")
            else:
                print(f"[Warn] 유저 정보 변경 동기화 실패 (성공 0건): {after.display_name} ({after.id})")

        except Exception as e:
            print(f"[Error] 유저 정보 변경 이벤트 처리 중 예외 발생: {e}")
            await self.send_staff_error_log(
                after.guild, 
                after, 
                "시스템 예외 (System Exception)", 
                f"내부 동기화 프로세스 실행 중 예외가 발생했습니다.\n**에러**: {e}"
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """가입 신청(Apply to Join) 승인 직후 유저에게 안내 DM 발송"""
        if member.bot:
            return

        discord_id = str(member.id)
        try:
            # DM 전송
            embed = discord.Embed(
                title="🎉 RPG 서버 가입 완료!",
                description=(
                    f"**RPG 서버**에 오신 것을 진심으로 환영합니다~\n\n"
                    "**가이드** 채널의 안내를 따라가며 정식 모험가가 되어보세요!\n\n"
                ),
                color=discord.Color.green()
            )
            await member.send(embed=embed)
            print(f"[Onboarding] {member.display_name} ({discord_id})님에게 승인 안내 DM 발송 완료")
        except discord.Forbidden:
            # DM 차단 유저는 조용히 무시 (포기)
            print(f"[Onboarding] {member.display_name} ({discord_id})님이 DM을 차단하여 알림 발송을 생략했습니다.")
        except Exception as e:
            print(f"[Onboarding Error] {member.display_name} ({discord_id}) 가입 이벤트 처리 중 오류: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """서버 퇴장 시 DB에서 유저 정보 삭제"""
        try:
            discord_id = str(member.id)
            affected_rows = await asyncio.to_thread(delete_user_from_db, discord_id)
            if affected_rows > 0:
                await delete_cache("cache:jobs:all")
                await delete_cache("cache:main_page:all")
                print(f"[Info] 퇴장 유저 삭제 완료: {member.display_name} ({discord_id})")
        except Exception as e:
            print(f"[Error] 퇴장 유저 삭제 중 오류: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        """실시간 음성 상태 감지 최적화 (Redis 연동 및 캐싱)"""
        if member.bot:
            return

        from src.database.cache import is_redis_disabled
        if is_redis_disabled:
            return

        # 입장 판별 (이전 채널 없음, 이후 채널 있음)
        is_join = before.channel is None and after.channel is not None
        # 퇴장 판별 (이전 채널 있음, 이후 채널 없음)
        is_leave = before.channel is not None and after.channel is None

        if not (is_join or is_leave):
            return

        try:
            discord_id = str(member.id)
            mc_uuid = None
            mc_username = ""

            # 1. Redis 캐시에서 맵핑 정보 획득 시도 (DB I/O 배제 - JSON 파싱)
            cached_data = await redis_client.get(f"rpgsync:user_mc:{discord_id}")

            if cached_data:
                try:
                    data = json.loads(cached_data)
                    mc_uuid = data.get("uuid")
                    mc_username = data.get("username", "")
                except Exception as parse_err:
                    print(f"[Voice Event] 캐시 파싱 실패: {parse_err}")
            
            if not mc_uuid:
                # 2. 캐시 유실 시 백업용 DB 1회성 조회 및 재캐싱
                info = await asyncio.to_thread(get_user_minecraft_info, discord_id)
                if info:
                    mc_uuid = info["uuid"]
                    mc_username = info["username"]
                    # Redis에 재캐싱 (JSON 구조)
                    cache_data = {
                        "uuid": mc_uuid,
                        "username": mc_username
                    }
                    await redis_client.set(f"rpgsync:user_mc:{discord_id}", json.dumps(cache_data, ensure_ascii=False))

            if not mc_uuid:
                return

            if is_join:
                # 음성 채널 입장 -> active_minecraft_users Set에 추가
                await redis_client.sadd("active_minecraft_users", mc_uuid)
                print(f"[Voice Event] 입장 감지 SADD: {member.display_name} ({mc_uuid})")

            elif is_leave:
                # 음성 채널 퇴장 -> active_minecraft_users Set에서 제거
                await redis_client.srem("active_minecraft_users", mc_uuid)
                print(f"[Voice Event] 퇴장 감지 SREM: {member.display_name} ({mc_uuid})")
                
                # 실시간 퇴장 이벤트 Pub/Sub 발행
                payload = {
                    "uuid": mc_uuid,
                    "minecraft_username": mc_username
                }
                await publish_message("rpgsync:voice_leave", payload)
                print(f"[Voice Event] 퇴장 Pub/Sub 발행 완료: {member.display_name}")

        except Exception as e:
            print(f"[Voice Event Error] 음성 이벤트 처리 오류: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(UserEvent(bot))
