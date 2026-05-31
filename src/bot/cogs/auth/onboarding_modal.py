import discord
import aiohttp
import json
import re
import os
import asyncio
from src.database.auth import register_verified_user
from src.database.cache import redis_client

def format_uuid(raw_uuid: str) -> str:
    """하이픈 없는 32자리 UUID를 표준 36자리(8-4-4-4-12) 소문자 포맷으로 정규화 변환"""
    raw_uuid = raw_uuid.lower().replace("-", "").strip()
    if len(raw_uuid) != 32:
        return raw_uuid
    return f"{raw_uuid[:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}-{raw_uuid[16:20]}-{raw_uuid[20:]}"

class UserNicknameVerificationModal(discord.ui.Modal, title="성인 인증 정보 입력"):
    """성인인증 전용 팝업 입력 모달"""

    kr_name = discord.ui.TextInput(
        label="한글 닉네임",
        placeholder="예: 홍길동 (한글 및 숫자 1~3자 제한)",
        min_length=1,
        max_length=10,
        required=True
    )

    mc_name = discord.ui.TextInput(
        label="마인크래프트 닉네임",
        placeholder="예: Steve (정품 닉네임, 대소문자 정확히 입력)",
        min_length=2,
        max_length=30,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 1. 인터랙션 지연 (API 및 Redis/DB 쿼리 타임아웃 대비)
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        raw_kr = self.kr_name.value.strip()
        raw_mc = self.mc_name.value.strip()

        # 2. 한글 닉네임 정밀 정규식 검사 (공백 제거 후 1~3자 체크)
        clean_kr = raw_kr.replace(" ", "")
        if not re.match("^[가-힣0-9]{1,3}$", clean_kr):
            await interaction.followup.send(
                "❌ **한글 닉네임 입력 오류**\n"
                "한글 닉네임은 한글과 숫자로 구성된 1~3글자만 허용됩니다. (공백 제외)",
                ephemeral=True
            )
            return

        # 2글자인 경우 글자 사이에 공백 1칸 삽입 규격 적용 (예: "홍길" -> "홍 길")
        if len(clean_kr) == 2:
            final_kr = f"{clean_kr[0]} {clean_kr[1]}"
        else:
            final_kr = clean_kr

        # 3. Mojang API 정품 계정 비동기 검증 (전역 세션 재사용 및 예외 폴백 적용)
        uuid_36 = None
        real_mc_name = raw_mc
        
        # 전역 ClientSession 획득
        bot_session = interaction.client.session if hasattr(interaction.client, "session") and interaction.client.session else None
        
        try:
            if bot_session and not bot_session.closed:
                # 전역 세션 재사용
                async with bot_session.get(f"https://api.mojang.com/users/profiles/minecraft/{raw_mc}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_uuid = data.get("id")
                        real_mc_name = data.get("name", raw_mc)
                        if raw_uuid:
                            uuid_36 = format_uuid(raw_uuid)
                    elif response.status == 429:
                        await interaction.followup.send(
                            "⚠️ 현재 마인크래프트 정품 조회 서버 요청이 혼잡합니다. 잠시 후 다시 제출해주세요.",
                            ephemeral=True
                        )
                        return
            else:
                # 폴백용 단발 세션 생성
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as fallback_session:
                    async with fallback_session.get(f"https://api.mojang.com/users/profiles/minecraft/{raw_mc}") as response:
                        if response.status == 200:
                            data = await response.json()
                            raw_uuid = data.get("id")
                            real_mc_name = data.get("name", raw_mc)
                            if raw_uuid:
                                uuid_36 = format_uuid(raw_uuid)
                        elif response.status == 429:
                            await interaction.followup.send(
                                "⚠️ 현재 마인크래프트 정품 조회 서버 요청이 혼잡합니다. 잠시 후 다시 제출해주세요.",
                                ephemeral=True
                            )
                            return
        except Exception as e:
            print(f"[Onboarding Modal] Mojang API 연동 중 오류 발생: {e}")
            # API 연동 도중 에러가 나면 봇 다운을 방지하고 일반 예외 피드백 처리
            await interaction.followup.send(
                "⚠️ 마인크래프트 계정 조회 시스템 장애가 발생했습니다. 반복 발생 시 스태프에게 문의해주세요.",
                ephemeral=True
            )
            return

        # 4. 조회 실패 시 Redis 기반 오입력 실패 락 관리
        if not uuid_36:
            fail_key = f"rpgsync:fail:{user_id}"
            
            # Redis를 이용해 실패 카운트 INCR (비연결 상태일 경우 봇 자체 메모리로 백업 구동 방어)
            try:
                fail_count = await redis_client.incr(fail_key)
                if fail_count == 1:
                    await redis_client.expire(fail_key, 3600)  # 최초 1회에만 1시간 TTL 부여
            except Exception as redis_err:
                print(f"[Cache Error] Redis 실패 키 설정 오류: {redis_err}")
                fail_count = 1  # Redis 연결 실패 시 기본값 처리

            # 3회 연속 실패 시 락 및 스태프 긴급 알림
            if fail_count >= 3:
                staff_channel_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
                staff_role_id = int(os.getenv("STAFF_ROLE_ID", 0))
                staff_channel = interaction.guild.get_channel(staff_channel_id) if interaction.guild else None

                if staff_channel:
                    staff_mention = f"<@&{staff_role_id}>" if staff_role_id else "@스태프"
                    embed = discord.Embed(
                        title="🚨 성인인증 오입력 초과 락 발생",
                        description=(
                            f"유저: **{interaction.user.display_name}** (ID: `{interaction.user.id}`)\n"
                            f"채널: {interaction.channel.mention}\n"
                            f"내용: 마인크래프트 정품 계정 입력 3회 연속 실패하여 모달 입력을 차단했습니다."
                        ),
                        color=discord.Color.red()
                    )
                    await staff_channel.send(
                        content=f"{staff_mention} 스태프의 확인 및 리셋 조치가 필요합니다.",
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=True) # 역할 멘션 활성화
                    )

                await interaction.followup.send(
                    "❌ **성인 인증 시도 초과**\n"
                    "마인크래프트 계정 확인에 3회 연속 실패했습니다. 입력 기회가 잠금 처리되었습니다. "
                    "스태프가 확인 및 잠금 해제를 완료할 때까지 잠시 기다려주세요.",
                    ephemeral=True
                )
                return

            await interaction.followup.send(
                f"❌ 존재하지 않는 마인크래프트 정품 계정입니다.\n"
                f"스펠링 및 대소문자를 확인해 주세요. (현재 입력 실패 횟수: {fail_count} / 3)",
                ephemeral=True
            )
            return

        # 5. 검증 성공 시 DB 업서트 및 Redis 영구 캐싱
        try:
            # 5.1. DB 저장 (기본적으로 음성 바이패스는 False)
            server_role = interaction.user.top_role.name if interaction.user.top_role else "유저"
            db_success = await asyncio.to_thread(
                register_verified_user,
                user_id,
                final_kr,
                server_role,
                uuid_36,
                real_mc_name,
                False
            )
            
            # UNIQUE 제약조건 위반 에러 가로채기
            if db_success == "UUID_DUPLICATE":
                await interaction.followup.send(
                    "❌ **인증 실패**\n제출하신 마인크래프트 정품 계정(UUID)은 **이미 다른 모험가님이 연동하여 사용 중**입니다.",
                    ephemeral=True
                )
                return
            elif db_success == "MC_NAME_DUPLICATE":
                await interaction.followup.send(
                    "❌ **인증 실패**\n제출하신 마인크래프트 닉네임은 **이미 연동되어 사용 중**입니다. 정확한 정품 닉네임을 다시 입력해주세요.",
                    ephemeral=True
                )
                return
            elif not db_success:
                raise Exception("DB register_verified_user 실행 결과 False 반환")

            # 5.2. Redis 단방향 매핑 영구 캐시 등록 (DB I/O 0화 목적 - JSON 확장)
            cache_data = {
                "uuid": uuid_36,
                "username": real_mc_name
            }
            await redis_client.set(f"rpgsync:user_mc:{user_id}", json.dumps(cache_data, ensure_ascii=False))

            # 5.3. 성공했으므로 Redis 실패 세션 삭제
            await redis_client.delete(f"rpgsync:fail:{user_id}")

        except Exception as db_err:
            print(f"[DB/Cache Error] 성인인증 완료 정보 적재 실패: {db_err}")
            await interaction.followup.send(
                "⚠️ 성인 인증 처리 도중 시스템 데이터베이스 연동 오류가 발생했습니다. 스태프에게 즉시 보고해 주세요.",
                ephemeral=True
            )
            return

        # 6. 디스코드 서버 별명 수정 (한글닉네임 포맷)
        new_nick = f"{final_kr}ㅣ백수"
        # 디스코드 별명 최대 32자 제한 엄수
        if len(new_nick) > 32:
            new_nick = new_nick[:32]
        
        try:
            await interaction.user.edit(nick=new_nick, reason="성인인증 모달 입력 검증 완료 변경")
        except discord.Forbidden:
            # 봇보다 권한이 높은 유저(서버 소유자 등)인 경우 수정 실패 무시
            print(f"[Warning] {interaction.user.display_name}의 별명을 수정할 권한이 없습니다.")

        # 7. 유저 피드백 Embed 발송 (UUID 완전 배제)
        user_embed = discord.Embed(
            title="✅ 닉네임 설정 성공",
            description=(
                f"마인크래프트 정품 계정 검증 및 닉네임 설정이 정상 완료되었습니다.\n\n"
                f"**한글 닉네임:** {final_kr}\n"
                f"**마크 닉네임:** {real_mc_name}"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(
            content="정보가 임시 저장되었습니다. 아래 안내에 따라 인증을 계속 진행해주세요.",
            embed=user_embed,
            ephemeral=True
        )

        # 8. 스태프 검수용 로그 전송 (UUID 상세 포함)
        staff_channel_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
        staff_channel = interaction.guild.get_channel(staff_channel_id) if interaction.guild else None
        if staff_channel:
            staff_embed = discord.Embed(
                title="📋 성인인증 대기 정보 제출",
                description=(
                    f"유저: **{interaction.user.display_name}** (ID: `{interaction.user.id}`)\n"
                    f"채널: {interaction.channel.mention}\n\n"
                    f"**제출된 한글 닉네임:** {final_kr}\n"
                    f"**제출된 마크 닉네임:** {real_mc_name}\n"
                    f"**정품 UUID:** `{uuid_36}`"
                ),
                color=discord.Color.blue()
            )
            await staff_channel.send(embed=staff_embed)

        # 9. 신분증(민증) 스크린샷 업로드 가이드 발송
        guide_embed = discord.Embed(
            title="📸 주민등록증 스크린샷 업로드 안내",
            description=(
                "마지막 인증 단계입니다.\n\n"
                "1. **주민등록증 사진**을 이 프라이빗 채널에 업로드해 주세요.\n"
                "   - **주의:** 생년(예: 000101) 부분 외의 모든 민감 정보(주민번호 뒷자리, 주소, 얼굴 등)는 **반드시 모자이크 또는 가림 처리**하셔야 합니다.\n"
                "2. 사진 업로드 후, 승인 처리를 진행할 때까지 잠시 대기해주세요.\n\n"
                "-# 사진 확인 완료 후 티켓은 완전 삭제되어 이미지 유출 우려가 전혀 없습니다."
            ),
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=guide_embed)
