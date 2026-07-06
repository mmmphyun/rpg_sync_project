import discord
from discord import app_commands
from discord.ext import commands
import asyncio

from src.bot.utils.checks import has_staff_privilege, StaffPermissionRequired
from src.database.nickname_format import get_nickname_formats, save_nickname_formats


class NicknameFormatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="닉네임양식설정", description="유저 닉네임에서 닉네임과 직업명을 추출할 양식을 추가/수정합니다.")
    @app_commands.describe(
        part_count="구분자로 쪼개었을 때 나오는 총 조각(파트)의 개수 (예: 3)",
        nickname_index="실제 한글 닉네임이 들어있는 조각의 번호 (1-based)",
        job_index="직업명이 들어있는 조각의 번호 (1-based)",
        delimiter="조각을 나누는 구분자 문자 (기본값: ㅣ)",
        staff_index="스태프 역할 식별자가 들어있는 조각의 번호 (선택 사항, 1-based)"
    )
    @app_commands.guild_only()
    @has_staff_privilege()
    async def set_nickname_format(
        self,
        interaction: discord.Interaction,
        part_count: int,
        nickname_index: int,
        job_index: int,
        delimiter: str = "ㅣ",
        staff_index: int = -1
    ):
        print(f"[Debug] set_nickname_format slash command. part_count: {part_count}, nick_idx: {nickname_index}, job_idx: {job_index}")

        # 1. 아규먼트 정합성 검증
        if part_count < 1:
            return await interaction.response.send_message("❌ 인덱스 개수(part_count)는 1 이상이어야 합니다.", ephemeral=True)
        
        if not (1 <= nickname_index <= part_count):
            return await interaction.response.send_message(f"❌ 닉네임 인덱스는 1 이상 {part_count} 이하여야 합니다.", ephemeral=True)

        if not (1 <= job_index <= part_count):
            return await interaction.response.send_message(f"❌ 직업명 인덱스는 1 이상 {part_count} 이하여야 합니다.", ephemeral=True)

        if staff_index != -1 and not (1 <= staff_index <= part_count):
            return await interaction.response.send_message(f"❌ 스태프 인덱스는 1 이상 {part_count} 이하거나 -1이어야 합니다.", ephemeral=True)

        # 인덱스 중복 체크
        used_indices = {nickname_index, job_index}
        if staff_index != -1:
            if staff_index in used_indices:
                return await interaction.response.send_message("❌ 각 인덱스 번호는 중복될 수 없습니다.", ephemeral=True)

        if nickname_index == job_index:
            return await interaction.response.send_message("❌ 각 인덱스 번호는 중복될 수 없습니다.", ephemeral=True)

        if len(delimiter) == 0:
            return await interaction.response.send_message("❌ 구분자 문자는 공백일 수 없습니다.", ephemeral=True)

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # 2. DB 조회 (비동기 스레드 분리)
            formats = await asyncio.to_thread(get_nickname_formats)
            if not isinstance(formats, list):
                formats = []

            # 3. 새로운/업데이트할 포맷 정의
            new_fmt = {
                "part_count": part_count,
                "delimiter": delimiter,
                "nickname_index": nickname_index,
                "job_index": job_index,
                "staff_index": staff_index
            }

            # 동일한 part_count가 있는지 확인 후 업데이트 또는 신규 삽입
            updated = False
            for i, fmt in enumerate(formats):
                if fmt.get("part_count") == part_count:
                    formats[i] = new_fmt
                    updated = True
                    break
            
            if not updated:
                formats.append(new_fmt)

            # part_count 기준으로 정렬 보존
            formats.sort(key=lambda x: x["part_count"])

            # 4. DB 저장
            success = await asyncio.to_thread(save_nickname_formats, formats)
            if not success:
                return await interaction.followup.send("❌ 데이터베이스 설정 저장에 실패했습니다.", ephemeral=True)

            # 5. 봇 전역 캐시 갱신
            self.bot.nickname_formats = formats
            print(f"[System] Nickname formats cache updated: {formats}")

            # 6. 성공 피드백 발송
            action_str = "수정" if updated else "등록"
            embed = discord.Embed(
                title=f"✅ 닉네임 양식 {action_str} 완료",
                color=discord.Color.green(),
                description=f"구분자 개수가 **{part_count}개**인 별명에 대한 파싱 룰이 적용되었습니다."
            )
            embed.add_field(name="구분자", value=f"`{delimiter}`", inline=True)
            embed.add_field(name="닉네임 인덱스", value=f"{nickname_index}번째 조각", inline=True)
            embed.add_field(name="직업명 인덱스", value=f"{job_index}번째 조각", inline=True)
            if staff_index != -1:
                embed.add_field(name="스태프 인덱스", value=f"{staff_index}번째 조각", inline=True)
            else:
                embed.add_field(name="스태프 인덱스", value="미사용", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"[Error] set_nickname_format 오류: {e}")
            await interaction.followup.send(f"❌ 설정 도중 예외가 발생했습니다: {e}", ephemeral=True)

    @set_nickname_format.error
    async def set_nickname_format_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """에러 핸들러 추가"""
        if isinstance(error, StaffPermissionRequired):
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(NicknameFormatCog(bot))
