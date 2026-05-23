import json
import time
import asyncio
import redis.asyncio as redis
from typing import Optional, Any
from src.config import (
    REDIS_URL,
    REDIS_CONNECT_TIMEOUT,
    REDIS_SOCKET_TIMEOUT,
    REDIS_HEALTHCHECK_INTERVAL
)

redis_client: Optional[redis.Redis] = None
is_redis_disabled: bool = False
last_health_check_time: float = 0.0
_is_checking_health: bool = False

async def init_redis_pool() -> None:
    """Initialize Async Redis Connection Pool"""
    global redis_client, is_redis_disabled, last_health_check_time
    try:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            retry_on_timeout=False
        )
        # 최초 예열 및 선제 핑 검사
        await redis_client.ping()
        is_redis_disabled = False
    except Exception as e:
        print(f"[Cache Error] Redis connection/ping failed: {e}", flush=True)
        is_redis_disabled = True
        last_health_check_time = time.time()

async def close_redis_pool() -> None:
    """Close Redis Connection Pool"""
    global redis_client
    if redis_client:
        await redis_client.aclose()

async def check_redis_health() -> None:
    """비동기 백그라운드 PING 검사 및 캐시 복구 토글"""
    global redis_client, is_redis_disabled, _is_checking_health, last_health_check_time
    try:
        if not redis_client:
            redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=False
            )
        print("[Cache Info] Running background Redis health check...", flush=True)
        await redis_client.ping()
        is_redis_disabled = False
        print("[Cache Success] Redis is recovered! Circuit Breaker Closed.", flush=True)
    except Exception as e:
        print(f"[Cache Error] Redis background health check failed: {e}", flush=True)
        is_redis_disabled = True
    finally:
        last_health_check_time = time.time()
        _is_checking_health = False

async def trigger_self_healing_if_needed() -> None:
    """캐시 비활성화 시 마지막 실패 이후 interval이 경과했다면 백그라운드 헬스체크 트리거"""
    global is_redis_disabled, last_health_check_time, _is_checking_health
    if not is_redis_disabled:
        return
    
    current_time = time.time()
    if current_time - last_health_check_time >= REDIS_HEALTHCHECK_INTERVAL:
        if not _is_checking_health:
            _is_checking_health = True
            asyncio.create_task(check_redis_health())

async def get_cache(key: str) -> Optional[Any]:
    """
    Get value from Redis Cache
    :param key: Cache key
    :return: Deserialized JSON object or None
    """
    global is_redis_disabled, last_health_check_time
    await trigger_self_healing_if_needed()
    if not redis_client or is_redis_disabled:
        return None
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        is_redis_disabled = True
        last_health_check_time = time.time()
        print(f"[Cache Error] get_cache failed for key {key} (Circuit Breaker Activated): {e}", flush=True)
        return None

async def set_cache(key: str, value: Any, ex: int = 3600) -> bool:
    """
    Set value to Redis Cache with TTL
    :param key: Cache key
    :param value: Serializable object
    :param ex: Expiration time in seconds (Default 1H)
    """
    global is_redis_disabled, last_health_check_time
    await trigger_self_healing_if_needed()
    if not redis_client or is_redis_disabled:
        return False
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await redis_client.set(key, serialized, ex=ex)
        return True
    except Exception as e:
        is_redis_disabled = True
        last_health_check_time = time.time()
        print(f"[Cache Error] set_cache failed for key {key} (Circuit Breaker Activated): {e}", flush=True)
        return False

async def delete_cache(key: str) -> bool:
    """Delete specific cache key (Invalidation)"""
    global is_redis_disabled, last_health_check_time
    await trigger_self_healing_if_needed()
    if not redis_client or is_redis_disabled:
        return False
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        is_redis_disabled = True
        last_health_check_time = time.time()
        print(f"[Cache Error] delete_cache failed for key {key} (Circuit Breaker Activated): {e}", flush=True)
        return False

async def publish_message(channel: str, message: Any) -> int:
    """Redis Pub/Sub을 통해 메시지를 발행합니다. 구독자 수를 반환합니다."""
    global is_redis_disabled, last_health_check_time
    await trigger_self_healing_if_needed()
    if not redis_client or is_redis_disabled:
        return 0
    try:
        serialized = json.dumps(message, ensure_ascii=False, default=str)
        receiver_count = await redis_client.publish(channel, serialized)
        return receiver_count
    except Exception as e:
        is_redis_disabled = True
        last_health_check_time = time.time()
        print(f"[Cache Error] publish_message failed (Circuit Breaker Activated): {e}", flush=True)
        return 0