import time
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.services.cache import cache_get, cache_set

_BASE = settings.TVMAZE_BASE_URL


async def _get(url: str, redis, cache_key: str, ttl: int) -> Optional[Any]:
    cached = await cache_get(redis, cache_key)
    if cached is not None:
        logger.info(f"TVMaze cache HIT: {cache_key}")
        return cached

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"TVMaze 404: {url}")
        elif e.response.status_code == 429:
            logger.warning(f"TVMaze rate-limited: {url}")
        else:
            logger.warning(f"TVMaze HTTP error {e.response.status_code}: {url}")
        return None
    except Exception as e:
        logger.warning(f"TVMaze network error for {url}: {e}")
        return None

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"TVMaze API call: {url} cache=MISS duration={elapsed}ms")
    await cache_set(redis, cache_key, data, ttl)
    return data


async def search_shows(query: str, redis) -> list[dict]:
    url = f"{_BASE}/search/shows?q={query}"
    key = f"tvmaze:search:{query.lower()}"
    result = await _get(url, redis, key, 3600)
    return result or []


async def get_show_details(tvmaze_id: int, redis, force_refresh: bool = False) -> Optional[dict]:
    key = f"tvmaze:show:{tvmaze_id}"
    if force_refresh:
        import redis.asyncio as aioredis
        try:
            await redis.delete(key)
        except Exception:
            pass
    url = f"{_BASE}/shows/{tvmaze_id}?embed[]=episodes&embed[]=nextepisode"
    return await _get(url, redis, key, settings.TVMAZE_CACHE_TTL)


async def get_episodes(tvmaze_id: int, redis) -> list[dict]:
    url = f"{_BASE}/shows/{tvmaze_id}/episodes"
    key = f"tvmaze:episodes:{tvmaze_id}"
    result = await _get(url, redis, key, settings.TVMAZE_CACHE_TTL)
    return result or []


async def check_season_count(tvmaze_id: int, redis, force_refresh: bool = False) -> int:
    episodes = await get_episodes(tvmaze_id, redis)
    if not episodes:
        details = await get_show_details(tvmaze_id, redis, force_refresh=force_refresh)
        if details:
            embedded = details.get("_embedded", {})
            eps = embedded.get("episodes", [])
            if eps:
                return max(e.get("season", 0) for e in eps)
        return 0
    return max(e.get("season", 0) for e in episodes) if episodes else 0


async def get_next_episode_info(tvmaze_id: int, redis) -> Optional[dict]:
    """Fetch the next episode details for a show. Returns dict with season/number/airdate or None."""
    # Force-refresh the show details to get latest nextepisode embed
    try:
        import redis.asyncio as aioredis
        key = f"tvmaze:show:{tvmaze_id}"
        await redis.delete(key)
    except Exception:
        pass
    details = await get_show_details(tvmaze_id, redis, force_refresh=False)
    if not details:
        return None
    next_ep = (details.get("_embedded") or {}).get("nextepisode") or {}
    if not next_ep:
        return None
    return {
        "season": next_ep.get("season"),
        "number": next_ep.get("number"),
        "airdate": next_ep.get("airdate"),
    }
