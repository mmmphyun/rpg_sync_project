import discord
import os
import asyncio
from discord import app_commands
from discord.ext import commands
from src.bot.cogs.core.base_cog import BaseCog
from src.database.connection import sync_users_to_db
from src.database.auth import check_user_exists, create_magic_token
from src.bot.utils.text_parser import parse_user_nickname

class AuthCmd(BaseCog):

    @app_commands.command(name="위키", description="위키 로그인을 위한 1회용 인증 링크를 발급합니다.")
    async def forum_login(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        discord_id = str(interaction.user.id)

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

                sync_result = await asyncio.to_thread(sync_users_to_db, user_data)
                if sync_result == 0:
                    await interaction.followup.send("유저 정보를 서버에 등록하는 중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)
                    return

            # 3. 토큰 발급 및 메시지 전송
            token = await asyncio.to_thread(create_magic_token, discord_id)
            domain = os.getenv("WEB_DOMAIN", "https://fossile-wiki.cloud")
            login_url = f"{domain}/api/v1/auth/login?token={token}"

            await interaction.followup.send(
                f"**인증 링크가 발급되었습니다.**\n"
                f"5분 안에 아래 링크를 클릭하여 접속하세요. 이 링크는 본인만 볼 수 있으며 1회만 사용 가능합니다.\n\n"
                f"[Fossile Wiki 로그인]({login_url})",
                ephemeral=True
            )
        except Exception as e:
            print(f"토큰 발급 에러: {e}")
            await interaction.followup.send("인증 링크 발급 중 시스템 오류가 발생했습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AuthCmd(bot))