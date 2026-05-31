import discord
import os
import asyncio
import re
from discord import app_commands
from discord.ext import commands
from src.bot.cogs.core.base_cog import BaseCog
from src.database.auth import create_magic_token, check_user_exists, is_guide_completed
from src.database.connection import sync_users_to_db
from src.bot.utils.text_parser import parse_user_nickname

class NicknameTriggerView(discord.ui.View):
    """티켓 내부 채널에 전송할 [닉네임 설정하기] 버튼 뷰"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="닉네임 설정하기", style=discord.ButtonStyle.success, custom_id="trigger_nickname_modal")
    async def trigger_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.bot.cogs.auth.onboarding_modal import UserNicknameVerificationModal
        await interaction.response.send_modal(UserNicknameVerificationModal())

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

        # 2. 고유 해시값 생성 (보안 및 심미성을 위해 Discord ID를 MD5 해싱한 8자리 사용)
        import hashlib
        user_id_str = str(interaction.user.id)
        user_hash = hashlib.md5(user_id_str.encode()).hexdigest()[:8]
        thread_name = f"인증-{interaction.user.display_name}-{user_hash}"
        
        # 중복 스레드 체크 (닉네임이 도중에 변경되었을 수 있으므로 고유 해시로 탐색)
        existing_thread = None
        for t in interaction.channel.threads:
            if t.name.endswith(f"-{user_hash}"):
                existing_thread = t
                break
        
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
            
            # 유저에게 안내 및 닉네임 설정 버튼 전송
            await thread.send(
                f"**{interaction.user.mention}님, 성인 인증을 위한 프라이빗 티켓이 생성되었습니다.**\n\n"
                f"아래 순서대로 진행됩니다.\n"
                f"1. 초록색 **[닉네임 설정하기]** 버튼을 눌러 정보를 입력해주세요.\n"
                f"2. 안내에 따라 **주민등록증 사진**을 올려주세요. (생년 부분 외 민감한 정보는 모두 가려주세요)\n"
                f"3. 승인 후 제공되는 가이드 링크를 통해 서버 시스템과 규칙을 숙지해주세요.\n\n"
                f"**[닉네임 정책]**\n"
                f"- 한글 닉네임: 한글 1~3글자 제한\n"
                f"스태프가 확인 후 승인할 때까지 잠시만 기다려주세요.",
                view=NicknameTriggerView()
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
                await staff_channel.send(embed=embed, view=TicketStaffView())
            
            await interaction.followup.send(
                f"프라이빗 인증 채널이 생성되었습니다: {thread.mention}\n해당 채널로 이동하여 신분증 사진을 올려주세요.", 
                ephemeral=True
            )
        except Exception as e:
            import traceback
            print(f"티켓 생성 상세 오류:\n{traceback.format_exc()}")
            await interaction.followup.send("티켓 생성 중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)

class TicketStaffView(discord.ui.View):
    """스태프 관제 채널에서 사용할 버튼 뷰 (Persistent)"""
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        staff_role_id = int(os.getenv("STAFF_ROLE_ID", 0))
        has_staff_role = any(role.id == staff_role_id for role in interaction.user.roles)
        has_manage_roles = interaction.user.guild_permissions.manage_roles

        if not (has_staff_role or has_manage_roles):
            await interaction.response.send_message("스태프 권한이 필요합니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="approve_user")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 메시지 Embed에서 유저 ID 및 스레드 ID 동적 복구
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("인증 메시지 정보를 읽을 수 없습니다.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        user_match = re.search(r'<@!?(\d+)>', embed.description)
        thread_match = re.search(r'<#(\d+)>', embed.description)

        if not user_match or not thread_match:
            await interaction.response.send_message("인증 대상 유저 및 채널 정보를 파싱할 수 없습니다.", ephemeral=True)
            return

        target_user_id = int(user_match.group(1))
        thread_id = int(thread_match.group(1))

        guild = interaction.guild
        member = guild.get_member(target_user_id)
        thread = guild.get_thread(thread_id)
        
        # 2. 버튼 비활성화 처리
        for child in self.children:
            child.disabled = True
        
        if member and thread:
            # 유저 스레드에 가이드 링크 직접 전송 (삭제하지 않음)
            await thread.send(
                f"{member.mention}님, 성인 인증이 승인되었습니다!\n아래 버튼을 눌러 가이드 페이지를 확인해주세요. 가이드 완료 시 이 채널은 자동 삭제됩니다.",
                view=GuideLinkView()
            )

        # 관제 채널 메시지 업데이트
        await interaction.response.edit_message(
            content=f"✅ **승인됨** (처리자: {interaction.user.mention})",
            embed=None,
            view=None
        )

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="reject_user")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("인증 메시지 정보를 읽을 수 없습니다.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        thread_match = re.search(r'<#(\d+)>', embed.description)

        if not thread_match:
            await interaction.response.send_message("채널 정보를 파싱할 수 없습니다.", ephemeral=True)
            return

        thread_id = int(thread_match.group(1))
        guild = interaction.guild
        thread = guild.get_thread(thread_id)

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
    """가이드 안내 채널에서 매직링크를 발급하는 버튼 뷰 (Persistent)"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="가이드 시작하기", style=discord.ButtonStyle.primary, custom_id="get_guide_link")
    async def get_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 스레드 이름 접미사 해시값 대조를 통해 100% 안전하게 본인 증명 복구
        import hashlib
        discord_id = str(interaction.user.id)
        user_hash = hashlib.md5(discord_id.encode()).hexdigest()[:8]

        if not interaction.channel.name.endswith(f"-{user_hash}"):
            await interaction.response.send_message("본인의 링크만 확인할 수 있습니다.", ephemeral=True)
            return
        
        # 비동기 DB 조회가 시작되기 전 인터랙션 응답 유효시간을 연장(defer)
        await interaction.response.defer(ephemeral=True)
        
        # 2. 이미 가이드 완료된 유저인지 체크하여 1차 방어 (중복 토큰 발급 및 불필요 트래픽 방지)
        try:
            completed = await asyncio.to_thread(is_guide_completed, discord_id)
            if completed:
                await interaction.followup.send(
                    "이미 가이드 서약을 완료하고 정식 멤버가 되셨습니다! 추가적인 가이드 진행이 필요하지 않습니다.",
                    ephemeral=True
                )
                return
        except Exception as e:
            print(f"[Onboarding] 가이드 완료 여부 확인 오류: {e}")
        
        # 3. 유저가 DB에 있는지 확인하고 없으면 등록
        try:
            user_exists = await asyncio.to_thread(check_user_exists, discord_id)
            if not user_exists:
                has_role = hasattr(interaction.user, 'top_role') and interaction.user.top_role
                role_name = interaction.user.top_role.name if has_role else "유저"
                display_name = interaction.user.display_name
                parsed = parse_user_nickname(display_name)

                user_data = [{
                    "discord_id": discord_id,
                    "nickname": parsed["nickname"],
                    "server_role": role_name,
                    "job_name": parsed["job_name"]
                }]
                await asyncio.to_thread(sync_users_to_db, user_data)
        except Exception as e:
            print(f"[DB Error] 유저 자동 등록 실패: {e}")

        # 4. 매직링크 생성
        try:
            token = await asyncio.to_thread(create_magic_token, discord_id)
            domain = os.getenv("WEB_DOMAIN", "https://fossile-wiki.cloud")
            guide_url = f"{domain}/api/v1/auth/login?token={token}&redirect=guide"

            await interaction.followup.send(
                f"아래 링크를 통해 가이드 페이지로 이동하여 내용을 확인해주세요.\n"
                f"모든 내용을 확인한 후 하단의 버튼을 누르면 정식 멤버가 됩니다.\n\n"
                f"[가이드 페이지 바로가기]({guide_url})",
                ephemeral=True
            )
        except Exception as e:
            print(f"매직링크 생성 에러: {e}")
            await interaction.followup.send("인증 링크 발급 중 시스템 오류가 발생했습니다.", ephemeral=True)

class FeedbackView(discord.ui.View):
    """미숙지/미동의 유저들이 이탈 전 피드백을 남기거나 구제받을 수 있는 버튼 뷰 (Persistent)"""
    def __init__(self):
        super().__init__(timeout=None)

    async def _send_feedback(self, interaction: discord.Interaction, reason: str):
        # 0. 인터랙션 응답 연장 및 지연
        await interaction.response.defer(ephemeral=True)

        # 1. 환경 변수에서 관제 채널 ID 로드
        verify_log_channel_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
        guild = interaction.guild
        log_channel = guild.get_channel(verify_log_channel_id) if guild else None

        if log_channel:
            try:
                # 100% 익명성 보장을 위해 어떠한 유저 ID나 닉네임도 기록하지 않음
                embed = discord.Embed(
                    title="피드백 수집",
                    description=f"유저 한 분이 가입 절차 중 아래 사유로 피드백을 제출했습니다.\n\n**사유:** {reason}",
                    color=discord.Color.orange()
                )
                await log_channel.send(embed=embed)
            except Exception as e:
                print(f"[Feedback] 익명 피드백 전송 실패: {e}")

        # 2. 유저에게는 안심 에페메럴 메시지 전송
        await interaction.followup.send(
            "소중한 의견을 전해주셔서 대단히 감사합니다. 본 피드백은 100% 익명으로 전달될 예정이며, "
            "더 안전하고 신뢰받는 서버가 될 수 있도록 시스템 개선에 적극 반영하겠습니다. 좋은 하루 되세요!",
            ephemeral=True
        )

    @discord.ui.button(label="🛡️ 개인정보 노출 걱정", style=discord.ButtonStyle.secondary, custom_id="feedback_privacy")
    async def privacy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_feedback(interaction, "개인정보 노출 걱정 (신분증 인증 불안)")

    @discord.ui.button(label="📖 가이드 규칙이 엄격함", style=discord.ButtonStyle.secondary, custom_id="feedback_rules")
    async def rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_feedback(interaction, "가이드 규칙이 너무 엄격함 (위키 및 규정 부담)")

    @discord.ui.button(label="⚙️ 절차가 복잡하고 귀찮음", style=discord.ButtonStyle.secondary, custom_id="feedback_complex")
    async def complex_proc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_feedback(interaction, "인증 절차가 너무 번거롭고 어려움")

    @discord.ui.button(label="❓ 기타 / 단순 마음 변화", style=discord.ButtonStyle.secondary, custom_id="feedback_etc")
    async def etc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_feedback(interaction, "기타 사유 / 단순 마음 변화 및 이탈")

    @discord.ui.button(label="🔄 다시 인증해볼래요", style=discord.ButtonStyle.success, custom_id="retry_verification", row=1)
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 0. 인터랙션 응답 연장 (권한이 즉시 날아가므로 에페메럴 처리 필수)
        await interaction.response.defer(ephemeral=True)

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send("서버 멤버만 이용할 수 있습니다.", ephemeral=True)
            return

        # 1. 환경 변수에서 역할 ID들 로드
        guide_role_id = int(os.getenv("GUIDE_ROLE_ID", 0))
        unverified_guide_role_id = int(os.getenv("UNVERIFIED_GUIDE_ROLE_ID", 0))
        unverified_auth_role_id = int(os.getenv("UNVERIFIED_AUTH_ROLE_ID", 0))
        adult_verify_channel_id = int(os.getenv("ADULT_AUDIT_LOG_CHANNEL_ID", 0))

        # 2. 역할 교체 준비
        guild = interaction.guild
        guide_role = guild.get_role(guide_role_id) if guild else None
        unverified_guide_role = guild.get_role(unverified_guide_role_id) if guild else None
        unverified_auth_role = guild.get_role(unverified_auth_role_id) if guild else None
        verify_channel = guild.get_channel(adult_verify_channel_id) if guild else None

        if not guide_role:
            await interaction.followup.send("시스템 역할 설정(GUIDE_ROLE_ID)이 올바르지 않습니다. 관리자에게 문의하세요.", ephemeral=True)
            return

        roles_to_remove = []
        if unverified_guide_role and unverified_guide_role in member.roles:
            roles_to_remove.append(unverified_guide_role)
        if unverified_auth_role and unverified_auth_role in member.roles:
            roles_to_remove.append(unverified_auth_role)

        # 3. 역할 교체 적용
        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="유저 요청으로 미인증 상태 역할 복구 및 재인증 진행")
            await member.add_roles(guide_role, reason="유저 요청으로 뉴비 역할 다시 복구")
            
            verify_channel_mention = verify_channel.mention if verify_channel else "#성인인증"
            await interaction.followup.send(
                f"다시 생각해주셔서 감사합니다! 이제 아래 채널로 이동하여 다시 인증 및 가이드를 진행하실 수 있습니다.\n\n"
                f"👉 {verify_channel_mention} 채널로 이동하기",
                ephemeral=True
            )
        except Exception as e:
            print(f"[Onboarding Retry Error] 역할 교체 실패: {e}")
            await interaction.followup.send("역할을 변경하는 도중 오류가 발생했습니다. 관리자에게 권한 부여 상태를 문의해주세요.", ephemeral=True)

class OnboardingCmd(BaseCog):
    """온보딩 및 성인 인증 명령어를 관리하는 Cog"""

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """역할 변경 시점에 미인증 상태가 부여되었는지 체크하고 피드백 채널로 안전한 웰컴 멘션 안내 발송 (60초 뒤 폭파)"""
        # 1. 역할 변경이 아닐 경우 스킵
        if before.roles == after.roles:
            return

        # 2. 환경 변수에서 타겟 정보 로드
        unverified_guide_role_id = int(os.getenv("UNVERIFIED_GUIDE_ROLE_ID", 0))
        unverified_auth_role_id = int(os.getenv("UNVERIFIED_AUTH_ROLE_ID", 0))
        feedback_channel_id = int(os.getenv("FEEDBACK_CHANNEL_ID", 0))

        if not feedback_channel_id:
            return

        # 3. 변경 시점 신규 획득 역할 파싱
        before_role_ids = {r.id for r in before.roles}
        after_role_ids = {r.id for r in after.roles}
        newly_added_ids = after_role_ids - before_role_ids

        is_guide_unverified = unverified_guide_role_id in newly_added_ids
        is_auth_unverified = unverified_auth_role_id in newly_added_ids

        # 4. '미숙지' 또는 '미동의' 역할이 새로 주어졌다면 안내 멘션 발송
        if is_guide_unverified or is_auth_unverified:
            guild = after.guild
            channel = guild.get_channel(feedback_channel_id)
            if not channel:
                return
            
            try:
                # 1회성 알림 멘션 발송 (디스코드 채널 뱃지 유도를 위해)
                mention_msg = await channel.send(
                    f"{after.mention}님, 가입 절차 진행 중 **가이드 숙지 또는 인증 관련 미동의** 사유로 보류되었습니다. 🛑\n\n"
                    f"💡 **혹시 개인정보 노출이 많이 불안하셨나요?**\n"
                    f"주민번호 뒷자리, 상세주소, 얼굴 등 민감한 정보는 개인정보 보호를 위해 **필수로 가려서 올려주셔야 합니다.** 스태프는 오직 생년만 확인하고 사진은 **즉시 영구 삭제**하니, 안심하고 편하게 진행해 주세요!\n\n"
                    f"설명을 확인하고 다시 용기를 내어 모험을 시작하고 싶으시다면 초록색 **[🔄 다시 인증해볼래요]** 버튼을 눌러주세요. "
                    f"가입 절차 상 개선할 점이 있다면 위의 익명 버튼으로 피드백을 남겨주셔도 귀중한 도움이 됩니다. 😊",
                    allowed_mentions=discord.AllowedMentions(users=True)
                )

                # 프라이버시 보호 및 깔끔한 채널 상태 유지를 위해 60초(1분) 뒤 자동 메시지 삭제
                async def auto_delete_msg(msg: discord.Message, delay: int = 60):
                    await asyncio.sleep(delay)
                    try:
                        await msg.delete()
                    except Exception:
                        pass # 유저가 수동 삭제했거나 이미 교체 완료된 상황 무시

                # 백그라운드 태스크 구동
                asyncio.create_task(auto_delete_msg(mention_msg))

            except Exception as e:
                print(f"[Onboarding Listener Error] 안전한 웰컴 멘션 전송 실패: {e}")

    @app_commands.command(name="온보딩", description="성인 인증 버튼을 현재 채널에 생성합니다. (관리자 전용)")
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

    @app_commands.command(name="피드백", description="온보딩 이탈 유저용 익명 피드백 및 복구 버튼을 생성합니다. (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_feedback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="모험가님, 잠시만요! 🛑",
            description=(
                "이 채널까지 오게 되어 대단히 아쉽고 죄송한 마음입니다.\n\n"
                "혹시 서버 인증 단계나 규칙에 대해 부담스럽거나 걱정되는 부분이 있으셨나요?\n"
                "아래의 피드백 버튼을 사용해 의견을 남겨주시면 서버 발전에 큰 도움이 됩니다!\n\n"
                "**🔒 안심하고 눌러주세요!** 피드백은 실시간으로 전송되지 않으며, 다른 분들의 피드백과 섞여 일정한 시간 뒤에 익명으로 전달되어 스태프들은 누가 눌렀는지 절대 추적할 수 없습니다.\n\n"
                "**💡 다시 모험을 시작하고 싶으신가요?**\n"
                "설명을 읽고 마음이 바뀌셨다면 초록색 **[🔄 다시 인증해볼래요]** 버튼을 누르시면 "
                "다시 인증과 가이드를 시도하실 수 있습니다!\n\n"
                "*저희 화석 서버는 유저 한 분 한 분의 안전과 편안한 플레이를 가장 소중히 여깁니다.*"
            ),
            color=discord.Color.orange()
        )
        await interaction.response.send_message("피드백 및 복구 시스템 메시지를 생성합니다.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=FeedbackView())

async def setup(bot: commands.Bot):
    # Persistent Views 등록 (봇 재시작 시에도 버튼 작동을 위해)
    bot.add_view(NicknameTriggerView())
    bot.add_view(VerificationRequestView())
    bot.add_view(TicketStaffView())
    bot.add_view(GuideLinkView())
    bot.add_view(FeedbackView())
    await bot.add_cog(OnboardingCmd(bot))
