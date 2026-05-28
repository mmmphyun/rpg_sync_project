import discord
import re
import asyncio
import os
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.database.connection import sync_users_to_db
from src.database.auth import delete_user_from_db, update_user_voice_exit
from src.database.cache import delete_cache
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
        """음성 채널 퇴장 감지 및 시간 기록"""
        if member.bot:
            return

        # 이전 채널이 존재하고, 이동할 채널이 없는 경우 (완전 퇴장)
        if before.channel is not None and after.channel is None:
            try:
                discord_id = str(member.id)
                affected_rows = await asyncio.to_thread(update_user_voice_exit, discord_id)
                if affected_rows > 0:
                    print(f"[Info] 음성 채널 퇴장 시간 기록 완료: {member.display_name}")
            except Exception as e:
                print(f"[Error] 음성 채널 퇴장 시간 기록 실패: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(UserEvent(bot))
