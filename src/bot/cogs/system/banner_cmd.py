import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Optional

from src.bot.utils.s3_client import upload_to_r2, delete_from_r2
from src.database.banner import insert_banner, get_all_banner_urls, delete_all_banners
from src.database.cache import delete_cache
from src.bot.utils.checks import has_staff_privilege


class BannerCog(commands.GroupCog, name="배너"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="등록", description="메인 페이지용 배너 이미지를 R2에 업로드하고 DB에 등록합니다.")
    @app_commands.describe(
        image="등록할 배너 이미지 파일",
        link="배너 클릭 시 이동할 연결 링크 (선택 사항)",
        sort_order="배너 정렬 순서 (기본값: 0)"
    )
    @app_commands.guild_only()
    @has_staff_privilege()
    async def add_banner(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        link: Optional[str] = None,
        sort_order: int = 0
    ):
        print(f"[Debug] add_banner slash command triggered. link: {link}, sort_order: {sort_order}")
        
        # 1. 이미지 파일 검증
        MAX_BANNER_SIZE = 25 * 1024 * 1024
        if image.size > MAX_BANNER_SIZE:
            return await interaction.response.send_message(
                f"❌ 배너 이미지는 최대 25MB까지만 업로드 가능합니다. (현재: {image.size / (1024 * 1024):.2f}MB)",
                ephemeral=True
            )

        if not image.content_type or not image.content_type.startswith('image/'):
            return await interaction.response.send_message(
                "❌ 이미지 파일(PNG, JPG, GIF 등)만 업로드 가능합니다.",
                ephemeral=True
            )

        # defer 호출
        await interaction.response.defer(thinking=True)

        try:
            # 2. 이미지 바이트 읽기
            file_bytes = await image.read()

            # 3. R2 업로드 (동기 boto3 사용하므로 스레드 분리)
            print(f"[Debug] Uploading to R2: {image.filename}")
            r2_url = await asyncio.to_thread(
                upload_to_r2,
                file_bytes=file_bytes,
                filename=image.filename,
                content_type=image.content_type,
                folder_name="banners"
            )

            if not r2_url:
                print("[Debug] R2 upload failed.")
                return await interaction.followup.send("❌ R2 스토리지 업로드에 실패했습니다.")
            
            print(f"[Debug] R2 upload success: {r2_url}")

            # 4. DB 적재 (동기 psycopg2 사용하므로 스레드 분리)
            banner_data = {
                "image_url": r2_url,
                "link_url": link,
                "sort_order": sort_order,
                "is_active": True
            }

            print(f"[Debug] Inserting to DB: {banner_data}")
            await asyncio.to_thread(insert_banner, banner_data)
            print("[Debug] DB insertion success.")

            # 5. 캐시 삭제
            print("[Debug] Deleting cache.")
            await delete_cache("cache:main_page:all")
            print("[Debug] Cache deletion success.")

            # 6. 최종 완료 메시지
            embed = discord.Embed(title="✅ 배너 등록 완료", color=discord.Color.green())
            embed.add_field(name="R2 URL", value=r2_url, inline=False)
            embed.add_field(name="연결 링크", value=link if link else "없음", inline=True)
            embed.add_field(name="우선 순위", value=str(sort_order), inline=True)
            embed.set_thumbnail(url=r2_url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '배너 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")

    @app_commands.command(name="초기화", description="등록된 모든 배너를 DB 및 R2 저장소에서 완전 삭제하고 캐시를 초기화합니다.")
    @app_commands.guild_only()
    @has_staff_privilege()
    async def reset_banners(self, interaction: discord.Interaction):
        print("[Debug] reset_banners slash command triggered.")
        
        # defer 호출
        await interaction.response.defer(thinking=True)

        try:
            # 1. DB에서 모든 배너 URL 조회 (스레드 분리)
            print("[Debug] Fetching all banner URLs from DB.")
            urls = await asyncio.to_thread(get_all_banner_urls)
            print(f"[Debug] Found {len(urls)} banner URLs: {urls}")

            # 2. R2에서 물리적 파일 삭제 (스레드 분리)
            if urls:
                tasks = [asyncio.to_thread(delete_from_r2, url) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for url, res in zip(urls, results):
                    if isinstance(res, Exception):
                        print(f"[Error] Failed to delete {url} from R2: {res}")
                    elif not res:
                        print(f"[Warning] R2 deletion returned False for: {url}")
                    else:
                        print(f"[Debug] Successfully deleted {url} from R2.")

            # 3. DB 테이블 truncate (delete_all_banners) (스레드 분리)
            print("[Debug] Truncating banners table in DB.")
            deleted_count = await asyncio.to_thread(delete_all_banners)
            print(f"[Debug] DB banners table truncated. Deleted {deleted_count} rows.")

            # 4. 캐시 삭제
            print("[Debug] Deleting cache.")
            await delete_cache("cache:main_page:all")
            print("[Debug] Cache deletion success.")

            # 5. 완료 메시지 전송
            embed = discord.Embed(title="🧹 배너 전체 초기화 완료", color=discord.Color.red())
            embed.description = f"DB에서 배너 데이터 **{deleted_count}개**가 완전 삭제되었으며, R2 물리 저장소 및 캐시가 초기화되었습니다."
            await interaction.followup.send(embed=embed)

        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            if hasattr(interaction.client, "send_error_log"):
                await interaction.client.send_error_log(f"Exception in slash command '배너 {interaction.command.name if interaction.command else 'Unknown'}':\n{tb_str}")
            await interaction.followup.send(f"❌ [Error] 처리 중 예외 발생: {str(e)}")


async def setup(bot):
    await bot.add_cog(BannerCog(bot))