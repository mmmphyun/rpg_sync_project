import os
import sys
import traceback
import discord
import asyncio
import concurrent.futures
import json
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
from src.database import cache

# 환경변수 로드
load_dotenv()


# ---------------------------------------------------------------------
# Discord UI View 전역 에러 관제 Monkey Patch
# ---------------------------------------------------------------------
async def global_view_on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
    """모든 discord.ui.View 콜백 내부에서 터지는 예외를 캐치하여 에러 관제 채널로 전송"""
    tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    view_name = self.__class__.__name__
    item_name = item.label if hasattr(item, "label") else "Unknown"
    error_msg = f"Exception in UI View '{view_name}' (Item '{item_name}'):\n{tb_str}"

    print(error_msg, file=sys.stderr)

    # interaction.client(즉, Bot 인스턴스)의 send_error_log 파이프라인 호출
    if hasattr(interaction, "client") and hasattr(interaction.client, "send_error_log"):
        await interaction.client.send_error_log(error_msg)

    # 사용자에게 비정상 종료 알림 (에러가 전파되어 유저 화면이 굳는 것 방어)
    user_msg = "인터랙션 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요."
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(user_msg, ephemeral=True)
        else:
            await interaction.followup.send(user_msg, ephemeral=True)
    except Exception:
        pass

# View 클래스의 기본 on_error 메서드를 커스텀 핸들러로 글로벌 교체
discord.ui.View.on_error = global_view_on_error


class RPGSyncBot(commands.Bot):
    def __init__(self):
        # Intents 설정: 메시지 내용과 멤버 정보 접근 권한 필요
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.error_channel_id = int(os.getenv('ERROR_LOG_CHANNEL_ID', 0)) or None
        self.tree.on_error = self.on_app_command_error
        self.redis_listener_task = None
        self.session = None

    async def close(self):
        """봇 종료 시 전역 ClientSession 자원 안전 해제"""
        if self.session and not self.session.closed:
            await self.session.close()
            print("[HTTP] Bot aiohttp ClientSession closed.", flush=True)
        await super().close()

    async def send_error_log(self, error_content: str):
        """에러 관제 채널로 트레이스백 발송. Discord 메시지 제한(2000자) 고려하여 Truncate 처리."""
        if not self.error_channel_id:
            return

        try:
            channel = self.get_channel(self.error_channel_id)
            if not channel:
                try:
                    channel = await self.fetch_channel(self.error_channel_id)
                except (discord.NotFound, discord.Forbidden):
                    return

            if channel:
                if len(error_content) > 1900:
                    error_content = error_content[:1900] + "\n... [Truncated]"

                await channel.send(f"```py\n{error_content}\n```")
        except Exception as e:
            print(f"[Error Log Pipeline Failure] Failed to send error log to channel {self.error_channel_id}: {e}", file=sys.stderr)

    async def on_error(self, event_method: str, /, *args, **kwargs):
        """봇 이벤트(on_ready, on_message 등) 루프 내 Uncaught Exception 관제탑 전송"""
        exc_info = sys.exc_info()
        tb_str = "".join(traceback.format_exception(*exc_info))
        error_msg = f"Exception in bot event '{event_method}':\n{tb_str}"

        print(error_msg, file=sys.stderr)
        await self.send_error_log(error_msg)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Prefix 커맨드 실행 중 발생한 예외 전역 캐치"""
        if isinstance(error, commands.CommandNotFound):
            return

        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        error_msg = f"Exception in prefix command '{ctx.command}':\n{tb_str}"

        print(error_msg, file=sys.stderr)
        await self.send_error_log(error_msg)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Slash 커맨드 실행 중 발생한 예외 전역 캐치 및 유저 Fallback 응답"""
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        cmd_name = interaction.command.name if interaction.command else "Unknown"
        error_msg = f"Exception in slash command '{cmd_name}':\n{tb_str}"

        print(error_msg, file=sys.stderr)
        await self.send_error_log(error_msg)

        user_msg = "시스템 내부 오류가 발생했습니다. 관리자에게 문의하세요."
        if not interaction.response.is_done():
            await interaction.response.send_message(user_msg, ephemeral=True)
        else:
            await interaction.followup.send(user_msg, ephemeral=True)

    async def listen_to_redis(self):
        """Redis Pub/Sub을 구독하여 이벤트를 처리합니다. (초안정화 버전)"""
        while True:
            try:
                if not cache.redis_client:
                    await asyncio.sleep(1)
                    continue

                pubsub = cache.redis_client.pubsub()
                async with pubsub as ps:
                    await ps.subscribe("onboarding:complete", "rpgsync:reason_submitted")
                    print("[REDIS] Successfully subscribed to 'onboarding:complete' and 'rpgsync:reason_submitted'", flush=True)

                    while True:
                        # get_message(timeout=None)은 메시지가 올 때까지 무한 대기함
                        message = await ps.get_message(ignore_subscribe_messages=True, timeout=10.0)
                        if message:
                            channel = message.get("channel")
                            data_str = message.get("data")
                            if isinstance(data_str, bytes):
                                data_str = data_str.decode("utf-8")
                            if isinstance(channel, bytes):
                                channel = channel.decode("utf-8")

                            print(f"[REDIS] Received from {channel}: {data_str}", flush=True)
                            try:
                                if channel == "onboarding:complete":
                                    data = json.loads(data_str)
                                    asyncio.create_task(self.handle_onboarding_complete(data))
                                elif channel == "rpgsync:reason_submitted":
                                    # data_str: "uuid:username:reason"
                                    parts = data_str.split(":", 2)
                                    mc_uuid = parts[0] if len(parts) > 0 else ""
                                    username = parts[1] if len(parts) > 1 else ""
                                    reason = parts[2] if len(parts) > 2 else ""
                                    
                                    cog = self.get_cog("ReasonBypassCog")
                                    if cog:
                                        asyncio.create_task(cog.handle_reason_submitted(mc_uuid, username, reason))
                                    else:
                                        print("[REDIS] ReasonBypassCog not found to handle reason_submitted", flush=True)
                            except Exception as e:
                                print(f"[REDIS] Data parsing error: {e}", flush=True)
                        await asyncio.sleep(0.01) # CPU 과점 방지
            except Exception as e:
                if "Timeout" not in str(e):
                    print(f"[REDIS] Listener error: {e}. Reconnecting in 5s...", flush=True)
                    await asyncio.sleep(5)
                continue

    async def handle_onboarding_complete(self, data: dict):
        """가이드 완료 이벤트를 처리하여 유저 역할을 변경합니다."""
        discord_id = data.get("discord_id")
        if not discord_id:
            print("[ONBOARDING] No discord_id in message data", flush=True)
            return

        print(f"[ONBOARDING] Start processing for user {discord_id}", flush=True)
        
        # 모든 서버(Guild)에서 해당 유저를 찾아 역할 변경 시도
        for guild in self.guilds:
            member = guild.get_member(int(discord_id))
            if not member:
                continue

            print(f"[ONBOARDING] Found member {member.display_name} in guild {guild.name}", flush=True)
            try:
                # GUIDE_ROLE_ID를 '뉴비' 역할 ID로 활용
                newbie_role_id = int(os.getenv("GUIDE_ROLE_ID", 0))
                member_role_id = int(os.getenv("MEMBER_ROLE_ID", 0))
                
                newbie_role = guild.get_role(newbie_role_id)
                member_role = guild.get_role(member_role_id)

                if newbie_role:
                    await member.remove_roles(newbie_role)
                    print(f"[ONBOARDING] Removed Newbie role ({newbie_role_id}) from {member.display_name}", flush=True)
                else:
                    print(f"[ONBOARDING] Newbie role ({newbie_role_id}) not found in guild", flush=True)

                if member_role:
                    await member.add_roles(member_role)
                    print(f"[ONBOARDING] Added Member role ({member_role_id}) to {member.display_name}", flush=True)
                else:
                    print(f"[ONBOARDING] Member role ({member_role_id}) not found in guild", flush=True)
                
                # 온보딩 프라이빗 스레드 삭제 (개선안: Discord ID 해싱 접미사 매칭 기법)
                import hashlib
                user_hash = hashlib.md5(str(discord_id).encode()).hexdigest()[:8]
                
                # 기본 탐색 대상 채널 설정
                onboarding_parent_id = int(os.getenv("ADULT_VERIFY_LOG_CHANNEL_ID", 0))
                parent_channel = guild.get_channel(onboarding_parent_id)
                
                # 1단계: 지정된 부모 채널 내 스레드에서 먼저 고유 해시로 검색
                existing_thread = None
                if parent_channel and isinstance(parent_channel, discord.TextChannel):
                    for t in parent_channel.threads:
                        if t.name.endswith(f"-{user_hash}"):
                            existing_thread = t
                            break

                # 2단계: 부모 채널 설정이 누락되었거나 찾지 못했다면, 길드 전체의 캐시된 활성 스레드에서 검색 (폴백)
                if not existing_thread:
                    for t in guild.threads:
                        if t.name.endswith(f"-{user_hash}"):
                            existing_thread = t
                            break

                if existing_thread:
                    await existing_thread.send("가이드 확인이 완료되었습니다. 이 채널을 종료합니다.")
                    await asyncio.sleep(3)
                    await existing_thread.delete()
                    print(f"[ONBOARDING] Deleted thread '{existing_thread.name}' for user {discord_id}", flush=True)
                else:
                    print(f"[ONBOARDING] Verification thread with hash suffix '-{user_hash}' not found for user {discord_id}", flush=True)
                
                print(f"[ONBOARDING] Successfully finished for {member.display_name}", flush=True)
            except Exception as e:
                import traceback
                print(f"[ONBOARDING] Error processing {discord_id}: {traceback.format_exc()}", flush=True)

    async def setup_hook(self):
        """봇 구동 시 필요한 확장 모듈을 로드하고 명령어를 동기화합니다."""
        try:
            # 커넥션 풀을 관리할 TCPConnector 옵션(Stale Connection 방지) 구성
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(connector=connector)
            print("[HTTP] Global aiohttp ClientSession configured with TCPConnector.", flush=True)
        except Exception as http_err:
            print(f"[HTTP] Failed to initialize global session: {http_err}", flush=True)

        try:
            await cache.init_redis_pool()
            print("Redis connection pool initialized for Bot.", flush=True)
            # 리스너 즉시 시작
            self.redis_listener_task = asyncio.create_task(self.listen_to_redis())
        except Exception as e:
            print(f"Failed to initialize Redis pool: {e}", flush=True)

        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        loop.set_default_executor(executor)
        print("Thread pool executor configured with max_workers=20", flush=True)

        extensions = [
            "src.bot.cogs.auth.auth_cmd",
            "src.bot.cogs.auth.onboarding_cmd",
            "src.bot.cogs.jobs.job_cmd",
            "src.bot.cogs.jobs.job_event",
            "src.bot.cogs.board.board_cmd",
            "src.bot.cogs.board.board_event",
            "src.bot.cogs.board.tip_event",
            "src.bot.cogs.users.user_event",
            "src.bot.cogs.users.user_cmd",
            "src.bot.cogs.users.reason_bypass",
            "src.bot.cogs.system.bulk_sync_cmd",
            "src.bot.cogs.system.banner_cmd"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"Loaded extension: {ext}", flush=True)
            except Exception as e:
                print(f"Failed to load extension {ext}: {e}", flush=True)

        # Persistent View 등록
        try:
            from src.bot.cogs.users.reason_bypass import ReasonBypassView
            self.add_view(ReasonBypassView())
            print("Successfully added persistent ReasonBypassView", flush=True)
        except Exception as e:
            print(f"Failed to add ReasonBypassView: {e}", flush=True)

        # 슬래시 명령어 동기화
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)", flush=True)
        except Exception as e:
            print(f"Failed to sync commands: {e}", flush=True)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})', flush=True)
        print('------', flush=True)
        
        # 봇이 참여 중인 모든 서버(Guild)에 슬래시 커맨드 강제 즉시 동기화
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"[Sync Success] Synced {len(synced)} command(s) to Guild: {guild.name} ({guild.id})", flush=True)
            except Exception as e:
                print(f"[Sync Error] Failed to sync to Guild {guild.name}: {e}", flush=True)

        # 봇 재부팅 시 기존 음성 접속 유저 동적 동기화 예열 (Bulk 최적화 버전)
        print("[Warm-up] Starting bulk voice status sync for existing members...", flush=True)
        
        discord_ids = []
        for guild in self.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        discord_ids.append(str(member.id))

        if not discord_ids:
            print("[Warm-up Info] No active voice users found at startup.", flush=True)
            return

        active_uuids = []
        missed_ids = []

        # 1. Redis user_mc JSON 캐시 1차 대조 (최속의 처리)
        for d_id in discord_ids:
            try:
                cached_data = await cache.redis_client.get(f"rpgsync:user_mc:{d_id}")
                if cached_data:
                    import json
                    data = json.loads(cached_data)
                    active_uuids.append(data.get("uuid"))
                else:
                    missed_ids.append(d_id)
            except Exception as e:
                missed_ids.append(d_id)

        # 2. 캐시 유실된 유저들만 딱 1번의 Bulk Query로 DB 일괄 복구
        if missed_ids:
            try:
                from src.database.auth import get_users_minecraft_info_bulk
                db_results = await asyncio.to_thread(get_users_minecraft_info_bulk, missed_ids)
                
                for res in db_results:
                    d_id = res["discord_id"]
                    mc_uuid = res["uuid"]
                    mc_name = res["username"]
                    active_uuids.append(mc_uuid)
                    
                    # Redis 캐시 복구 저장
                    import json
                    cache_data = {"uuid": mc_uuid, "username": mc_name}
                    await cache.redis_client.set(f"rpgsync:user_mc:{d_id}", json.dumps(cache_data, ensure_ascii=False))
            except Exception as db_err:
                print(f"[Warm-up Error] Bulk DB Query failed: {db_err}", flush=True)

        # 3. Redis active_minecraft_users Set 일괄 주입
        if active_uuids:
            try:
                await cache.redis_client.sadd("active_minecraft_users", *active_uuids)
                print(f"[Warm-up Success] Synced {len(active_uuids)} active user(s) to Redis cache via Bulk Pipeline.", flush=True)
            except Exception as redis_err:
                print(f"[Warm-up Error] Failed to SADD bulk users: {redis_err}", flush=True)

        # 4. 복구 파이프라인 트리거 (ReasonBypassCog.on_ready_recovery_check 실행)
        print("[Recovery] Triggering on_ready_recovery_check for ReasonBypassCog...", flush=True)
        try:
            cog = self.get_cog("ReasonBypassCog")
            if cog:
                for guild in self.guilds:
                    asyncio.create_task(cog.on_ready_recovery_check(guild))
                print("[Recovery] Recovery tasks scheduled successfully.", flush=True)
            else:
                print("[Recovery Error] ReasonBypassCog not loaded yet.", flush=True)
        except Exception as recovery_err:
            print(f"[Recovery Error] Failed to trigger recovery check: {recovery_err}", flush=True)



if __name__ == '__main__':
    bot = RPGSyncBot()
    discord_token = os.getenv('DISCORD_TOKEN')

    if not discord_token:
        raise ValueError("DISCORD_TOKEN이 .env 파일에 설정되지 않았습니다.")

    bot.run(discord_token)
