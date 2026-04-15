import discord
from discord.ext import commands
from src.database.queries import update_job_single_column


class SyncCmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="직업수정")
    @commands.has_permissions(administrator=True)
    async def update_job_command(self, ctx: commands.Context, job_name: str, column: str, *, value: str):
        """
        Usage: !직업수정 <직업명> <항목> <값>
        Example: !직업수정 다크메이지 img https://example.com/img.png
        """
        try:
            affected = update_job_single_column(job_name, column, value)

            if affected > 0:
                await ctx.send(f"✅ `{job_name}`의 `{column}` 항목이 성공적으로 업데이트되었습니다.")
            else:
                await ctx.send(f"⚠️ `{job_name}` 직업을 찾을 수 없습니다.")

        except ValueError as ve:
            await ctx.send(f"❌ 지원하지 않는 항목입니다. 지원 항목: range, position, resource, img, photo1~4")
        except Exception as e:
            await ctx.send(f"❌ 데이터베이스 처리 중 오류가 발생했습니다: {str(e)}")

    @update_job_command.error
    async def update_job_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("사용법: `!직업수정 <직업명> <항목> <값>`\n예시: `!직업수정 다크메이지 range 원거리`")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("명령어 실행 권한이 없습니다.")


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCmd(bot))