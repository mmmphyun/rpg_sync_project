import discord
import re
import asyncio
import os
from discord.ext import commands

from src.bot.cogs.core.base_cog import BaseCog
from src.database.connection import sync_users_to_db
from src.database.auth import delete_user_from_db, update_user_voice_exit
from src.database.cache import delete_cache

class UserEvent(BaseCog):

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """유저 입장 시 뉴비 역할 부여 확인 (온보딩 보완용 더블체크)"""
        if member.bot:
            return

        # 온보딩 완료를 위해 잠시 대기 (10초)
        await asyncio.sleep(10)
        
        newbie_role_id = int(os.getenv("GUIDE_ROLE_ID", 0))
        if newbie_role_id == 0:
            print("[Warn] GUIDE_ROLE_ID 환경변수가 설정되지 않았습니다.")
            return

        role = member.guild.get_role(newbie_role_id)
        if role and role not in member.roles:
            try:
                await member.add_roles(role)
                print(f"[Join] {member.display_name}에게 뉴비 역할(더블체크) 부여 완료.")
            except Exception as e:
                print(f"[Error] 뉴비 역할 부여 실패: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """유저 닉네임 변경 감지 및 단건 동기화"""
        if before.bot:
            return

        if before.display_name == after.display_name:
            return

        # 닉네임 파싱 (양식: 후원등급ㅣ직급ㅣ닉네임ㅣ직업명)
        display_name = after.display_name
        parts = [p.strip() for p in re.split(r'[ㅣ\|]', display_name)]

        job_name = None
        actual_nickname = display_name
        server_role = "유저"

        if len(parts) >= 4:
            server_role = parts[-3]
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
        elif len(parts) == 3:
            server_role = parts[-3]
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
        elif len(parts) == 2:
            actual_nickname = parts[-2]
            job_name = parts[-1].replace(" ", "").lower()
        elif len(parts) == 1:
            actual_nickname = parts[0]

        if not server_role:
            server_role = "유저"
        if job_name and not job_name.strip():
            job_name = None

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
