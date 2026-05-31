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

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """유저 닉네임 변경 감지 및 단건 동기화"""
        if before.bot:
            return

        if before.display_name == after.display_name:
            return

        # 공통 파서 유틸리티를 사용하여 닉네임 파싱 및 정제
        parsed = parse_user_nickname(after.display_name)
        actual_nickname = parsed["nickname"]
        server_role = parsed["server_role"]
        job_name = parsed["job_name"]

        user_data = {
            "discord_id": str(after.id),
            "nickname": actual_nickname,
            "server_role": server_role,
            "job_name": job_name
        }

        success_count = await asyncio.to_thread(sync_users_to_db, [user_data])

        if success_count > 0:
            await delete_cache("cache:jobs:all")
            print(f"[Info] 유저 정보 변경 동기화 완료: {before.display_name} -> {after.display_name} ({after.id})")
        else:
            print(f"[Warn] 유저 정보 변경 동기화 실패: {after.display_name} ({after.id})")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """가입 신청(Apply to Join) 승인 직후 유저에게 안내 DM 발송"""
        if member.bot:
            return

        discord_id = str(member.id)
        try:
            # DM 전송
            embed = discord.Embed(
                title="🎉 화석 서버 가입 완료!",
                description=(
                    f"**화석 서버**에 오신 것을 진심으로 환영합니다~\n\n"
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
