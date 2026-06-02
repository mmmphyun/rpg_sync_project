import os
import json
import asyncio
import discord
from discord.ext import commands

from src.database.auth import get_user_by_uuid, update_user_bypass_status, get_users_minecraft_info_bulk
from src.database.cache import redis_client, publish_message

class ReasonBypassView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    def create_view(cls, mc_uuid: str) -> "ReasonBypassView":
        view = cls()
        approve_btn = discord.ui.Button(
            label="승인",
            style=discord.ButtonStyle.green,
            custom_id=f"rpgsync:bypass_approve:{mc_uuid}"
        )
        deny_btn = discord.ui.Button(
            label="거절",
            style=discord.ButtonStyle.red,
            custom_id=f"rpgsync:bypass_deny:{mc_uuid}"
        )
        view.add_item(approve_btn)
        view.add_item(deny_btn)
        return view

    async def handle_click(self, interaction: discord.Interaction, action: str, mc_uuid: str):
        lock_key = f"rpgsync:processing_reason:{mc_uuid}"
        
        # 1. Redis 분산 락 시도 (5초 만료)
        acquired = await redis_client.set(lock_key, "1", ex=5, nx=True)
        if not acquired:
            await interaction.response.send_message("이미 처리 중이거나 완료된 사유입니다.", ephemeral=True)
            return

        try:
            # 2. 락 획득 후 interaction.response.defer() 처리
            await interaction.response.defer()

            # 3. 화면 상의 모든 컴포넌트(버튼) 비활성화 처리 및 즉각 갱신
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await interaction.message.edit(view=self)

            if action == "approve":
                # 4. 승인 버튼 처리 (임시 우회이므로 DB 갱신 없이 오직 플러그인에 승인 신호만 전달)
                user_info = await asyncio.to_thread(get_user_by_uuid, mc_uuid)
                if not user_info or not user_info.get("discord_id"):
                    await interaction.followup.send("디스코드 연동 미완료 유저는 승인이 불가합니다.", ephemeral=True)
                    return

                # Redis Pub/Sub 발행
                await publish_message("rpgsync:bypass_granted", {"uuid": mc_uuid})
                
                # 메시지 내용 및 초록색 테두리 갱신
                if interaction.message.embeds:
                    embed = interaction.message.embeds[0]
                    new_embed = discord.Embed.from_dict(embed.to_dict())
                    new_embed.color = discord.Color.green()
                    await interaction.message.edit(
                        content=f"임시 승인 완료 (담당 스태프: {interaction.user.mention})",
                        embed=new_embed,
                        view=self
                    )

            elif action == "deny":
                # 5. 거절 버튼 처리
                # Redis Pub/Sub 발행
                await publish_message("rpgsync:kick_player", {
                    "uuid": mc_uuid,
                    "reason": "이탈 사유 승인 거절 (스태프에 의한 킥)"
                })
                
                # 메시지 내용 및 빨간색 테두리 갱신
                if interaction.message.embeds:
                    embed = interaction.message.embeds[0]
                    new_embed = discord.Embed.from_dict(embed.to_dict())
                    new_embed.color = discord.Color.red()
                    await interaction.message.edit(
                        content=f"거절 완료 (담당 스태프: {interaction.user.mention})",
                        embed=new_embed,
                        view=self
                    )

        except Exception as e:
            print(f"[ReasonBypassView] Error handling click: {e}")
            await interaction.followup.send("인터랙션 처리 중 알 수 없는 에러가 발생했습니다.", ephemeral=True)
        finally:
            # 6. 락 해제
            await redis_client.delete(lock_key)


class RecoveryBypassView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="일괄 승인 복구",
            style=discord.ButtonStyle.danger,
            custom_id="rpgsync:bulk_bypass_recovery"
        ))

    async def handle_bulk_recovery(self, interaction: discord.Interaction):
        lock_key = "rpgsync:bulk_bypass_recovery"
        
        # 1. 락 획득 시도 (5초 만료)
        acquired = await redis_client.set(lock_key, "1", ex=5, nx=True)
        if not acquired:
            await interaction.response.send_message("이미 일괄 복구가 진행 중입니다.", ephemeral=True)
            return

        try:
            # 2. defer 및 비활성화 갱신
            await interaction.response.defer()
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await interaction.message.edit(view=self)

            # 3. 실시간 비정상 유저 전수 탐색
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("길드 정보를 찾을 수 없습니다.", ephemeral=True)
                return

            active_mc_uuids = await redis_client.smembers("active_minecraft_users")
            if not active_mc_uuids:
                await interaction.followup.send("현재 마크에 접속 중인 유저가 없습니다.", ephemeral=True)
                return

            voice_discord_ids = []
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        voice_discord_ids.append(str(member.id))

            voice_connected_uuids = set()
            missed_ids = []
            
            for d_id in voice_discord_ids:
                cached_data = await redis_client.get(f"rpgsync:user_mc:{d_id}")
                if cached_data:
                    try:
                        data = json.loads(cached_data)
                        if data.get("uuid"):
                            voice_connected_uuids.add(data.get("uuid"))
                    except Exception:
                        missed_ids.append(d_id)
                else:
                    missed_ids.append(d_id)

            if missed_ids:
                db_results = await asyncio.to_thread(get_users_minecraft_info_bulk, missed_ids)
                for res in db_results:
                    voice_connected_uuids.add(res["uuid"])

            active_mc_uuids = {uuid.decode("utf-8") if isinstance(uuid, bytes) else uuid for uuid in active_mc_uuids}
            no_voice_uuids = active_mc_uuids - voice_connected_uuids

            success_count = 0
            fail_count = 0
            
            # 대상자 일괄 임시 승인 발행 (DB 영구 갱신 배제)
            for uuid in no_voice_uuids:
                user_info = await asyncio.to_thread(get_user_by_uuid, uuid)
                if user_info:
                    discord_id = user_info.get("discord_id")
                    if discord_id:
                        await publish_message("rpgsync:bypass_granted", {"uuid": uuid})
                        success_count += 1
                    else:
                        fail_count += 1 # 미연동 유저는 임시 승인 불가
                else:
                    fail_count += 1

            # 4. 임베드 및 메시지 초록색 갱신
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                new_embed = discord.Embed.from_dict(embed.to_dict())
                new_embed.color = discord.Color.green()
                new_embed.description = (
                    f"**일괄 임시 승인 복구 완료**\n"
                    f"- 담당 스태프: {interaction.user.mention}\n"
                    f"- 성공: {success_count}명 / 실패(또는 미연동): {fail_count}명"
                )
                await interaction.message.edit(embed=new_embed, view=self)

        except Exception as e:
            print(f"[RecoveryBypassView] Error handling bulk recovery: {e}")
            await interaction.followup.send("일괄 복구 처리 중 알 수 없는 에러가 발생했습니다.", ephemeral=True)
        finally:
            await redis_client.delete(lock_key)


class ReasonBypassCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 스태프 알림 로그 채널 ID 로드
        try:
            self.log_channel_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
        except ValueError:
            self.log_channel_id = 0

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Persistent View를 보완하기 위한 전역 인터랙션 리스너"""
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")
        if not custom_id:
            return

        # 단건 승인/거절 버튼 처리
        if custom_id.startswith("rpgsync:bypass_approve:"):
            mc_uuid = custom_id.split("rpgsync:bypass_approve:")[1]
            view = ReasonBypassView.create_view(mc_uuid)
            await view.handle_click(interaction, "approve", mc_uuid)
        elif custom_id.startswith("rpgsync:bypass_deny:"):
            mc_uuid = custom_id.split("rpgsync:bypass_deny:")[1]
            view = ReasonBypassView.create_view(mc_uuid)
            await view.handle_click(interaction, "deny", mc_uuid)
        # 일괄 복구 버튼 처리
        elif custom_id == "rpgsync:bulk_bypass_recovery":
            view = RecoveryBypassView()
            await view.handle_bulk_recovery(interaction)

    async def handle_reason_submitted(self, mc_uuid: str, username: str, reason: str):
        """Redis Pub/Sub을 통해 제출된 사유 메시지를 렌더링하고 View를 첨부하여 전송합니다."""
        try:
            user_info = await asyncio.to_thread(get_user_by_uuid, mc_uuid)
            
            channel = self.bot.get_channel(self.log_channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(self.log_channel_id)
                except Exception as fe:
                    print(f"[ReasonBypassCog] 로그 채널 획득 실패: {fe}", flush=True)
                    return

            if user_info and user_info.get("discord_id"):
                discord_id = user_info["discord_id"]
                nickname = user_info["nickname"] or "없음"
                mc_username = user_info["minecraft_username"] or username or "없음"

                embed = discord.Embed(
                    title="📋 음성 이탈 사유 제출 (연동 완료)",
                    description="디스코드 연동 유저의 음성 채널 미접속 사유가 접수되었습니다.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="디스코드 계정", value=f"<@{discord_id}> ({nickname})", inline=False)
                embed.add_field(name="마인크래프트 UUID", value=f"`{mc_uuid}`", inline=True)
                embed.add_field(name="마인크래프트 닉네임", value=f"`{mc_username}`", inline=True)
                embed.add_field(name="제출 사유", value=f"```\n{reason}\n```", inline=False)
            else:
                embed = discord.Embed(
                    title="⚠️ [경고: 디스코드 연동 미완료] 음성 이탈 사유 제출",
                    description="디스코드와 연동되지 않은 마크 유저의 사유가 접수되었습니다. (승인 불가)",
                    color=discord.Color.orange()
                )
                embed.add_field(name="마인크래프트 UUID", value=f"`{mc_uuid}`", inline=True)
                embed.add_field(name="마인크래프트 닉네임", value=f"`{username}`", inline=True)
                embed.add_field(name="제출 사유", value=f"```\n{reason}\n```", inline=False)

            view = ReasonBypassView.create_view(mc_uuid)
            await channel.send(embed=embed, view=view)
            print(f"[ReasonBypassCog] 사유 카드 발송 완료 (UUID: {mc_uuid})", flush=True)

        except Exception as e:
            import traceback
            print(f"[ReasonBypassCog] 사유 처리 오류: {traceback.format_exc()}", flush=True)

    async def on_ready_recovery_check(self, guild: discord.Guild):
        """복구 파이프라인: 마크 접속 중이나 음성 및 DB 예외 처리가 되지 않은 유저들을 탐색해 일괄 복구 버튼 카드를 발송합니다."""
        try:
            active_mc_uuids = await redis_client.smembers("active_minecraft_users")
            if not active_mc_uuids:
                print("[Recovery] active_minecraft_users Set이 비어있어 복구를 건너뜁니다.", flush=True)
                return

            voice_discord_ids = []
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        voice_discord_ids.append(str(member.id))

            voice_connected_uuids = set()
            missed_ids = []

            for d_id in voice_discord_ids:
                cached_data = await redis_client.get(f"rpgsync:user_mc:{d_id}")
                if cached_data:
                    try:
                        data = json.loads(cached_data)
                        if data.get("uuid"):
                            voice_connected_uuids.add(data.get("uuid"))
                    except Exception:
                        missed_ids.append(d_id)
                else:
                    missed_ids.append(d_id)

            if missed_ids:
                db_results = await asyncio.to_thread(get_users_minecraft_info_bulk, missed_ids)
                for res in db_results:
                    voice_connected_uuids.add(res["uuid"])

            active_mc_uuids = {uuid.decode("utf-8") if isinstance(uuid, bytes) else uuid for uuid in active_mc_uuids}
            no_voice_uuids = active_mc_uuids - voice_connected_uuids

            if not no_voice_uuids:
                print("[Recovery] 비정상 접속 유저가 없습니다.", flush=True)
                return

            target_users = []
            for uuid in no_voice_uuids:
                user_info = await asyncio.to_thread(get_user_by_uuid, uuid)
                if user_info:
                    if not user_info.get("bypass_voice_check"):
                        target_users.append({
                            "uuid": uuid,
                            "username": user_info.get("minecraft_username") or "알 수 없음",
                            "discord_id": user_info.get("discord_id")
                        })
                else:
                    target_users.append({
                        "uuid": uuid,
                        "username": "미연동 유저",
                        "discord_id": None
                    })

            if not target_users:
                print("[Recovery] 복구 검토가 필요한 미예외 유저가 없습니다.", flush=True)
                return

            channel = self.bot.get_channel(self.log_channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(self.log_channel_id)
                except Exception:
                    print("[Recovery] 복구 채널을 획득하지 못했습니다.", flush=True)
                    return

            user_list_str = "\n".join([
                f"- `{u['username']}` ({u['uuid']}) " + (f"- <@{u['discord_id']}>" if u['discord_id'] else "[미연동]")
                for u in target_users[:15]
            ])
            if len(target_users) > 15:
                user_list_str += f"\n...외 {len(target_users) - 15}명"

            embed = discord.Embed(
                title="🚨 비상 복구: 음성 접속 예외 일괄 구제 필요",
                description=(
                    f"현재 마크 접속 중이나 음성 채널에 존재하지 않고, DB 예외도 등록되지 않은 유저가 **{len(target_users)}명** 식별되었습니다.\n\n"
                    f"**[복구 대상 목록]**\n{user_list_str}\n\n"
                    f"아래 [일괄 승인 복구] 버튼을 누르면 이 유저들이 즉시 예외 등록되어 킥에서 면제됩니다."
                ),
                color=discord.Color.red()
            )

            view = RecoveryBypassView()
            await channel.send(embed=embed, view=view)
            print(f"[Recovery] 복구 비상 카드 전송 완료 ({len(target_users)}명)", flush=True)

        except Exception as e:
            import traceback
            print(f"[Recovery Error] 복구 체크 수행 중 오류: {traceback.format_exc()}", flush=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReasonBypassCog(bot))
