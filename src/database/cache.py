import json
import redis.asyncio as redis
from typing import Optional, Any
from src.config import REDIS_URL

redis_client: Optional[redis.Redis] = None

async def init_redis_pool() -> None:
    """Initialize Async Redis Connection Pool"""
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def close_redis_pool() -> None:
    """Close Redis Connection Pool"""
    global redis_client
    if redis_client:
        await redis_client.aclose()

async def get_cache(key: str) -> Optional[Any]:
    """
    Get value from Redis Cache
    :param key: Cache key
    :return: Deserialized JSON object or None
    """
    if not redis_client:
        return None
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"[Cache Error] get_cache failed for key {key}: {e}", flush=True)
        return None

async def set_cache(key: str, value: Any, ex: int = 3600) -> bool:
    """
    Set value to Redis Cache with TTL
    :param key: Cache key
    :param value: Serializable object
    :param ex: Expiration time in seconds (Default 1H)
    """
    if not redis_client:
        return False
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await redis_client.set(key, serialized, ex=ex)
        return True
    except Exception as e:
        print(f"[Cache Error] set_cache failed for key {key}: {e}", flush=True)
        return False

async def delete_cache(key: str) -> bool:
    """Delete specific cache key (Invalidation)"""
    if not redis_client:
        return False
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        print(f"[Cache Error] delete_cache failed for key {key}: {e}", flush=True)
        return False