import discord
from discord import app_commands
from discord.ext import commands
import asyncio

from src.bot.utils.s3_client import upload_to_r2
from src.database.banner import insert_banner


class BannerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="배너등록", description="메인 페이지용 배너 이미지를 R2에 업로드하고 DB에 등록합니다.")
    @app_commands.describe(
        image="등록할 배너 이미지 파일 (필수)",
        link="배너 클릭 시 이동할 URL (선택)",
        sort_order="노출 우선순위 (숫자가 클수록 우선 노출, 기본값 0)"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_banner(
            self,
            interaction: discord.Interaction,
            image: discord.Attachment,
            link: str = None,
            sort_order: int = 0
    ):
        await interaction.response.defer(ephemeral=True)

        if not image.content_type or not image.content_type.startswith('image/'):
            return await interaction.followup.send("❌ 이미지 파일(PNG, JPG, GIF 등)만 업로드 가능합니다.")

        try:
            file_bytes = await image.read()

            r2_url = await asyncio.to_thread(
                upload_to_r2,
                file_bytes=file_bytes,
                filename=image.filename,
                content_type=image.content_type,
                folder_name="banners"
            )

            if not r2_url:
                return await interaction.followup.send("❌ R2 스토리지 업로드에 실패했습니다.")

            banner_data = {
                "image_url": r2_url,
                "link_url": link,
                "sort_order": sort_order,
                "is_active": True
            }

            await asyncio.to_thread(insert_banner, banner_data)

            embed = discord.Embed(title="✅ 배너 등록 완료", color=discord.Color.green())
            embed.add_field(name="R2 URL", value=r2_url, inline=False)
            embed.add_field(name="연결 링크", value=link if link else "없음", inline=True)
            embed.add_field(name="우선 순위", value=str(sort_order), inline=True)
            embed.set_thumbnail(url=r2_url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"[Error] 배너 등록 커맨드 예외 발생: {e}")
            await interaction.followup.send("❌ 배너 등록 중 서버 내부 오류가 발생했습니다.")


async def setup(bot):
    await bot.add_cog(BannerCog(bot))