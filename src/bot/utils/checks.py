import os
import discord
from discord import app_commands

class StaffPermissionRequired(app_commands.errors.CheckFailure):
    """스태프 권한 요구 예외 클래스"""
    pass

def has_staff_privilege():
    """스태프 역할 보유자 및 관리자(administrator) 권한 검증 전역 데코레이터"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise StaffPermissionRequired("이 명령어는 서버(Guild) 내에서만 실행 가능합니다.")

        staff_role_id = int(os.getenv("STAFF_ROLE_ID", 0))
        is_staff = any(role.id == staff_role_id for role in interaction.user.roles) if staff_role_id else False
        is_admin = interaction.user.guild_permissions.administrator

        if is_staff or is_admin:
            return True
        
        # 권한이 없을 경우 전용 예외를 발생시켜 커스텀 핸들링 유도
        raise StaffPermissionRequired("이 명령어를 실행할 스태프 권한이 없습니다.")
    
    return app_commands.check(predicate)
