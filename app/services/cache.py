import json
from typing import Any, Optional
import redis.asyncio as aioredis
from loguru import logger


async def cache_get(redis: aioredis.Redis, key: str) -> Optional[Any]:
    try:
        value = await redis.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        logger.warning(f"Redis GET failed for key={key}: {e}")
    return None


async def cache_set(redis: aioredis.Redis, key: str, value: Any, ttl: int) -> None:
    try:
        await redis.set(key, json.dumps(value), ex=ttl)
    except Exception as e:
        logger.warning(f"Redis SET failed for key={key}: {e}")


async def cache_delete(redis: aioredis.Redis, key: str) -> None:
    try:
        await redis.delete(key)
    except Exception as e:
        logger.warning(f"Redis DELETE failed for key={key}: {e}")


async def cache_get_bytes(redis: aioredis.Redis, key: str) -> Optional[bytes]:
    try:
        value = await redis.get(key)
        return value
    except Exception as e:
        logger.warning(f"Redis GET (bytes) failed for key={key}: {e}")
    return None


async def cache_set_bytes(redis: aioredis.Redis, key: str, value: bytes, ttl: int) -> None:
    try:
        await redis.set(key, value, ex=ttl)
    except Exception as e:
        logger.warning(f"Redis SET (bytes) failed for key={key}: {e}")
