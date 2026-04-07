from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.core.config import settings


async def season_check_job() -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.crud import get_series_for_season_check
    from app.services import tvmaze as tvmaze_svc
    from app.services.search import web_search

    logger.info("Season check job started")
    cutoff = timedelta(days=settings.SEASON_CHECK_MONTHS * 30)
    now = datetime.utcnow()

    checked = 0
    updated = 0

    # We need redis — fetch from app state via a workaround
    # The scheduler job runs in the same event loop as the app,
    # so we can import app state via a module-level holder
    from app.services.scheduler_state import get_redis, get_chroma

    redis = get_redis()
    if redis is None:
        logger.warning("Season check job: Redis not available, aborting")
        return

    async with AsyncSessionLocal() as db:
        series_list = await get_series_for_season_check(db)
        due = [
            s for s in series_list
            if s.last_season_check is None or (now - s.last_season_check) > cutoff
        ]
        logger.info(f"Season check: {len(due)} shows due out of {len(series_list)}")

        for series in due:
            try:
                new_count = await tvmaze_svc.check_season_count(
                    series.tvmaze_id, redis, force_refresh=True
                )
                checked += 1

                if new_count > series.total_seasons:
                    series.total_seasons = new_count
                    series.has_new_season = True
                    updated += 1
                    logger.info(f"New season detected: {series.name} → {new_count} seasons")
                elif new_count == 0:
                    # TVMaze had no data — try DDG
                    query = f"{series.name} new season release date {now.year}"
                    snippet = await web_search(query)
                    if any(kw in snippet.lower() for kw in ["season", "renewed", "confirmed"]):
                        logger.info(f"DDG fallback found info for: {series.name}")

                series.last_season_check = now
            except Exception as e:
                logger.error(f"Season check failed for {series.name}: {e}")
                series.last_season_check = now

        await db.commit()

    logger.info(
        f"Season check job complete: {checked} checked, {updated} updated"
    )


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        season_check_job,
        trigger="cron",
        hour=2,
        minute=0,
        id="season_check_daily",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
