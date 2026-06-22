import time
import jwt
from fastapi import APIRouter, Cookie, HTTPException
from mcstatus import JavaServer
from src.config import MINECRAFT_SERVER_ADDRESS, JWT_SECRET, JWT_ALGORITHM
from src.database.cache import redis_client, is_redis_disabled

router = APIRouter(
    tags=["server"]
)

# 인메모리 캐시 저장소 (60초 TTL)
cache = {
    "data": None,
    "last_updated": 0
}

CACHE_TTL = 60  # 60초 동안은 MC 서버를 찌르지 않고 캐시된 데이터 반환
SERVER_ADDRESS = MINECRAFT_SERVER_ADDRESS

_local_cooldown_time = 0


@router.get("/status")
async def get_server_status():
    current_time = time.time()

    # 캐시 데이터의 online 여부에 따라 TTL 다르게 적용 (정상 60초, 에러/오프라인 120초로 실패 시 핑 보호)
    ttl = CACHE_TTL
    if cache["data"] and not cache["data"].get("online", False):
        ttl = 120

    # 캐시가 존재하고 유효 시간이 지나지 않았다면 즉시 반환
    if cache["data"] and (current_time - cache["last_updated"] < ttl):
        return cache["data"]

    try:
        # 캐시가 만료되었거나 없을 때만 MC 서버로 실제 비동기 핑 전송 (타임아웃 2초 추가)
        mc_server = await JavaServer.async_lookup(SERVER_ADDRESS)
        status = await mc_server.async_status(timeout=2.0)

        result = {
            "online": True,
            "players": {
                "online": status.players.online,
                "max": status.players.max
            }
        }
    except Exception as e:
        print(f"MC Server Status Error: {e}")
        # 서버가 닫혀있거나 응답이 없을 경우 오프라인 처리
        result = {
            "online": False,
            "players": {
                "online": 0,
                "max": 0
            }
        }

    # 성공이든 실패든 그 결과를 캐싱하고 시간 갱신
    cache["data"] = result
    cache["last_updated"] = current_time

    return result


@router.post("/refresh")
async def refresh_server_status(forum_session: str = Cookie(None)):
    global _local_cooldown_time
    if not forum_session:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        role = payload.get("server_role")
        if role != "STAFF":
            raise HTTPException(status_code=403, detail="권한이 없습니다.")
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다.")

    current_time = time.time()
    cooldown_duration = 60
    cooldown_key = "rpgsync:server_refresh_cooldown"

    # 1. 쿨다운 검사
    is_cooldown = False
    remaining = 0

    if not is_redis_disabled:
        try:
            ttl = await redis_client.ttl(cooldown_key)
            if ttl > 0:
                is_cooldown = True
                remaining = ttl
        except Exception:
            # Redis 쿼리 실패 시 로컬 메모리 폴백
            if current_time - _local_cooldown_time < cooldown_duration:
                is_cooldown = True
                remaining = int(cooldown_duration - (current_time - _local_cooldown_time))
    else:
        # Redis 비활성화 시 로컬 메모리 쿨다운
        if current_time - _local_cooldown_time < cooldown_duration:
            is_cooldown = True
            remaining = int(cooldown_duration - (current_time - _local_cooldown_time))

    if is_cooldown:
        raise HTTPException(
            status_code=429,
            detail=f"새로고침 쿨타임 중입니다. ({remaining}초 남음)"
        )

    # 2. 쿨다운 락 설정
    if not is_redis_disabled:
        try:
            await redis_client.set(cooldown_key, "1", ex=cooldown_duration)
        except Exception:
            _local_cooldown_time = current_time
    else:
        _local_cooldown_time = current_time

    # 3. 강제 갱신 실행
    try:
        mc_server = await JavaServer.async_lookup(SERVER_ADDRESS)
        status = await mc_server.async_status(timeout=2.0)
        result = {
            "online": True,
            "players": {
                "online": status.players.online,
                "max": status.players.max
            }
        }
    except Exception as e:
        print(f"MC Server Force Refresh Error: {e}")
        result = {
            "online": False,
            "players": {
                "online": 0,
                "max": 0
            }
        }

    # 캐시 강제 업데이트
    cache["data"] = result
    cache["last_updated"] = current_time

    return result