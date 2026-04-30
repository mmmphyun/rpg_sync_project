import discord
from discord.ext import commands
import asyncio

from src.bot.utils.s3_client import upload_to_r2
from src.database.banner import insert_banner


class BannerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="배너등록", help="메인 페이지용 배너 이미지를 R2에 업로드하고 DB에 등록합니다.")
    @commands.has_permissions(administrator=True)  # 관리자 전용 권한 잠금
    async def add_banner(self, ctx: commands.Context, link: str = None, sort_order: int = 0):
        # 1. 첨부 파일 유무 확인
        if not ctx.message.attachments:
            return await ctx.send("❌ 등록할 배너 이미지 파일을 함께 업로드해주세요.")

        image = ctx.message.attachments[0]

        # 2. 이미지 파일 검증
        if not image.content_type or not image.content_type.startswith('image/'):
            return await ctx.send("❌ 이미지 파일(PNG, JPG, GIF 등)만 업로드 가능합니다.")

        # 3. 처리 중 메시지 전송 (R2 업로드 등 시간이 걸릴 수 있으므로)
        processing_msg = await ctx.send("⏳ 배너 이미지를 처리 중입니다...")

        try:
            # 4. 디스코드 서버에서 이미지 바이트 읽기
            file_bytes = await image.read()

            # 5. R2 업로드 (동기 라이브러리 boto3 사용 -> 스레드 분리 필수)
            r2_url = await asyncio.to_thread(
                upload_to_r2,
                file_bytes=file_bytes,
                filename=image.filename,
                content_type=image.content_type,
                folder_name="banners"
            )

            if not r2_url:
                return await processing_msg.edit(content="❌ R2 스토리지 업로드에 실패했습니다.")

            # 6. DB 적재 (동기 psycopg2 사용 -> 스레드 분리 필수)
            banner_data = {
                "image_url": r2_url,
                "link_url": link,
                "sort_order": sort_order,
                "is_active": True
            }

            # 실무 환경에 맞춰 insert_banner 함수는 구현되어야 합니다.
            await asyncio.to_thread(insert_banner, banner_data)

            # 7. 최종 완료 메시지로 수정
            embed = discord.Embed(title="✅ 배너 등록 완료", color=discord.Color.green())
            embed.add_field(name="R2 URL", value=r2_url, inline=False)
            embed.add_field(name="연결 링크", value=link if link else "없음", inline=True)
            embed.add_field(name="우선 순위", value=str(sort_order), inline=True)
            embed.set_thumbnail(url=r2_url)

            await processing_msg.edit(content=None, embed=embed)

        except Exception as e:
            print(f"[Error] 배너 등록 커맨드 예외 발생: {e}")
            await processing_msg.edit(content="❌ 배너 등록 중 서버 내부 오류가 발생했습니다.")


async def setup(bot):
    await bot.add_cog(BannerCog(bot))