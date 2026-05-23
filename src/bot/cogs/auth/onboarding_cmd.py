import discord
import os
import asyncio
import re
from discord import app_commands
from discord.ext import commands
from src.bot.cogs.core.base_cog import BaseCog
from src.database.auth import create_magic_token, check_user_exists
from src.database.connection import sync_users_to_db

class VerificationRequestView(discord.ui.View):
    """#성인인증 채널에 표시될 [성인 인증] 버튼 뷰"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="성인 인증 시작", style=discord.ButtonStyle.primary, custom_id="start_verification")
    async def start_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 0. 인터랙션 지연 (타임아웃 방지)
        await interaction.response.defer(ephemeral=True)

        # 1. 전역 쿨타임 체크 (분당 3회 제한)
        if not hasattr(self, "_creation_log"):
            self._creation_log = []
        
        import time
        current_time = time.time()
        self._creation_log = [t for t in self._creation_log if current_time - t < 60]
        
        if len(self._creation_log) >= 3:
            await interaction.followup.send(
                "현재 인증 요청이 많습니다. 잠시 후 다시 시도해주세요. (분당 최대 3회 생성 가능)", 
                ephemeral=True
            )
            return

        # 2. 중복 스레드 체크
        thread_name = f"인증-{interaction.user.display_name}"
        existing_thread = discord.utils.get(interaction.channel.threads, name=thread_name)
        
        if existing_thread:
            await interaction.followup.send(
                f"이미 생성된 인증 티켓이 있습니다: {existing_thread.mention}\n해당 채널에서 인증을 진행해주세요.", 
                ephemeral=True
            )
            return
        
        # 3. 프라이빗 스레드 생성
        try:
            thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread
            )
            self._creation_log.append(current_time)
            await thread.add_user(interaction.user)
            
            # 유저에게는 안내만
            await thread.send(
                f"**{interaction.user.mention}님, 성인 인증을 위한 프라이빗 티켓이 생성되었습니다.**\n\n"
                f"아래 내용을 순서대로 진행해주세요.\n"
                f"1. **주민등록증 사진**을 올려주세요. (뒷자리와 상세 주소는 가려주세요)\n"
                f"2. 서버에서 사용할 **닉네임**을 채팅창에 적어주세요.\n\n"
                f"**[닉네임 정책]**\n"
                f"- !!한글!! 1~3글자 제한\n"
                f"스태프가 확인 후 승인할 때까지 잠시만 기다려주세요."
            )
            
            # 스태프 관제 채널에 버튼 전송
            staff_channel_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
            staff_channel = interaction.guild.get_channel(staff_channel_id)
            
            if staff_channel:
                embed = discord.Embed(
                    title="새로운 성인 인증 요청",
                    description=f"유저: {interaction.user.mention} ({interaction.user.display_name})\n채널: {thread.mention}",
                    color=discord.Color.blue()
                )
                await staff_channel.send(embed=embed, view=TicketStaffView(interaction.user.id, thread.id))
            
            await interaction.followup.send(
                f"프라이빗 인증 채널이 생성되었습니다: {thread.mention}\n해당 채널로 이동하여 신분증 사진을 올려주세요.", 
                ephemeral=True
            )
        except Exception as e:
            import traceback
            print(f"티켓 생성 상세 오류:\n{traceback.format_exc()}")
            await interaction.followup.send("티켓 생성 중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)

class TicketStaffView(discord.ui.View):
    """스태프 관제 채널에서 사용할 버튼 뷰"""
    def __init__(self, target_user_id: int, thread_id: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.thread_id = thread_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("스태프 권한이 필요합니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="approve_user")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.target_user_id)
        thread = guild.get_thread(self.thread_id)
        
        # 감사 로그를 위해 버튼 비활성화 처리
        for child in self.children:
            child.disabled = True
        
        if member and thread:
            # 유저 스레드에 가이드 링크 직접 전송 (삭제하지 않음)
            await thread.send(
                f"{member.mention}님, 성인 인증이 승인되었습니다!\n아래 버튼을 눌러 가이드 페이지를 확인해주세요. 가이드 완료 시 이 채널은 자동 삭제됩니다.",
                view=GuideLinkView(member.id)
            )

        # 관제 채널 메시지 업데이트
        await interaction.response.edit_message(
            content=f"✅ **승인됨** (처리자: {interaction.user.mention})",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="reject_user")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        thread = guild.get_thread(self.thread_id)

        await interaction.response.edit_message(
            content=f"❌ **거절됨** (처리자: {interaction.user.mention})",
            embed=None,
            view=None
        )

        if thread:
            try:
                await thread.send("인증이 거절되었습니다. 이 채널은 즉시 삭제됩니다.")
                await asyncio.sleep(3)
                await thread.delete()
            except:
                pass

class GuideLinkView(discord.ui.View):
    """가이드 안내 채널에서 매직링크를 발급하는 버튼 뷰"""
    def __init__(self, target_user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="가이드 시작하기", style=discord.ButtonStyle.primary, custom_id="get_guide_link")
    async def get_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("본인의 링크만 확인할 수 있습니다.", ephemeral=True)
            return

        discord_id = str(interaction.user.id)
        
        # 1. 유저가 DB에 있는지 확인하고 없으면 등록
        try:
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

                user_data = [{
                    "discord_id": discord_id,
                    "nickname": actual_nickname,
                    "server_role": role_name,
                    "job_name": job_name
                }]
                await asyncio.to_thread(sync_users_to_db, user_data)
        except Exception as e:
            print(f"[DB Error] 유저 자동 등록 실패: {e}")

        # 2. 매직링크 생성
        try:
            token = await asyncio.to_thread(create_magic_token, discord_id)
            domain = os.getenv("WEB_DOMAIN", "https://fossile-wiki.cloud")
            guide_url = f"{domain}/api/v1/auth/login?token={token}&redirect=guide"

            await interaction.response.send_message(
                f"아래 링크를 통해 가이드 페이지로 이동하여 내용을 확인해주세요.\n"
                f"모든 내용을 확인한 후 하단의 버튼을 누르면 정식 멤버가 됩니다.\n\n"
                f"[가이드 페이지 바로가기]({guide_url})",
                ephemeral=True
            )
        except Exception as e:
            print(f"매직링크 생성 에러: {e}")
            await interaction.response.send_message("인증 링크 발급 중 시스템 오류가 발생했습니다.", ephemeral=True)

class OnboardingCmd(BaseCog):
    """온보딩 및 성인 인증 명령어를 관리하는 Cog"""

    @app_commands.command(name="온보딩세업", description="성인 인증 버튼을 현재 채널에 생성합니다. (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_onboarding(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="성인 인증",
            description=(
                "본 서버는 성인 전용 서버입니다.\n"
                "아래 버튼을 눌러 프라이빗 티켓을 생성하고, 신분증 확인을 진행해주세요.\n\n"
                "**준비물:** 신분증 사진 (뒷자리/상세주소 가림 처리 필수)"
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message("온보딩 시스템 메시지를 생성합니다.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=VerificationRequestView())

async def setup(bot: commands.Bot):
    # Persistent Views 등록 (봇 재시작 시에도 버튼 작동을 위해)
    bot.add_view(VerificationRequestView())
    await bot.add_cog(OnboardingCmd(bot))
