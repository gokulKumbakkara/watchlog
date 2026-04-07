# ══════════════════════════════════════════════════════════════
# CHROME EXTENSION INTEGRATION — IMPLEMENTATION GUIDE
# ══════════════════════════════════════════════════════════════
#
# This endpoint is ready. To build the Chrome extension:
#
# manifest.json permissions needed:
#   "tabs", "activeTab", "storage"
#   host_permissions: ["https://www.netflix.com/*",
#                      "https://www.disneyplus.com/*",
#                      "https://www.primevideo.com/*",
#                      "https://www.hotstar.com/*"]
#
# content.js — tab title parsing regexes:
#   Netflix  : /^(.+) - S(\d+):E(\d+)/
#   Disney+  : /^(.+) \| Season (\d+) \| Episode (\d+)/
#   Prime    : /^(.+) - Season (\d+), Episode (\d+)/
#   Hotstar  : /^(.+) - S(\d+) E(\d+)/
#
# Call this endpoint with:
#   POST {WATCHLOG_BASE_URL}/api/v1/extension/now-playing
#   Headers: { "X-Extension-Key": "<your key>", "Content-Type": "application/json" }
#   Body: { show_name, season, episode, source, timestamp }
#
# Store WATCHLOG_BASE_URL and extension key in chrome.storage.sync
# Debounce calls — only fire after 60 seconds on same episode
# ══════════════════════════════════════════════════════════════

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.extension import ExtensionPayload, ExtensionResponse
from app.services.crud import fuzzy_match_series

router = APIRouter(prefix="/extension", tags=["extension"])


def _verify_key(x_extension_key: str = Header(...)):
    if not secrets.compare_digest(x_extension_key, settings.EXTENSION_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid extension API key")


@router.post("/now-playing", response_model=ExtensionResponse)
async def now_playing(
    payload: ExtensionPayload,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_key),
):
    series = await fuzzy_match_series(db, payload.show_name)
    if not series:
        from loguru import logger
        logger.warning(f"Extension: unknown show_name={payload.show_name!r}")
        raise HTTPException(
            status_code=404,
            content={"error": "show not found", "show_name": payload.show_name},
        )

    # Idempotency check
    if series.current_season == payload.season and series.current_episode == payload.episode:
        return ExtensionResponse(
            updated=False,
            series_id=series.id,
            message=f"Already at S{payload.season:02d}E{payload.episode:02d} — no update needed.",
        )

    series.current_season = payload.season
    series.current_episode = payload.episode
    series.last_watched = payload.timestamp or datetime.utcnow()
    series.extension_source = payload.source
    series.updated_at = datetime.utcnow()
    await db.commit()

    return ExtensionResponse(
        updated=True,
        series_id=series.id,
        message=(
            f"Updated '{series.name}' to S{payload.season:02d}E{payload.episode:02d} "
            f"via {payload.source}."
        ),
    )


@router.get("/status")
async def extension_status():
    return {
        "configured": bool(settings.EXTENSION_API_KEY and settings.EXTENSION_API_KEY != "changeme"),
        "endpoint": "/api/v1/extension/now-playing",
    }
