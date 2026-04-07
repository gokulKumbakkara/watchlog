import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_db
from app.schemas.series import SeriesCreate, SeriesOut, SeriesUpdate, TVMazeSearchResult
from app.services import crud, tvmaze as tvmaze_svc
from app.services.auth import get_current_user
from app.services.ingestion import ingest_series

router = APIRouter(prefix="/series", tags=["series"])


@router.get("", response_model=list[SeriesOut])
async def list_series(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.get_series_list(db, user_id=current_user.id, status=status)


@router.get("/search", response_model=list[TVMazeSearchResult])
async def search_tvmaze(
    q: str = Query(..., min_length=1),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    redis = request.app.state.redis
    results = await tvmaze_svc.search_shows(q, redis)
    out = []
    for item in results[:8]:
        show = item.get("show", {})
        image = show.get("image") or {}
        network = show.get("network") or show.get("webChannel") or {}
        genres = show.get("genres", [])
        import re
        summary = show.get("summary") or ""
        summary = re.sub(r"<[^>]+>", "", summary)
        out.append(TVMazeSearchResult(
            tvmaze_id=show["id"],
            name=show["name"],
            poster_url=image.get("medium"),
            network=network.get("name"),
            genre=",".join(genres) if genres else None,
            status=show.get("status"),
            summary=summary or None,
            score=item.get("score", 0.0),
        ))
    return out


@router.post("", response_model=SeriesOut, status_code=201)
async def add_series(
    payload: SeriesCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    redis = request.app.state.redis
    chroma = request.app.state.chroma

    existing = await crud.get_series_by_tvmaze_id(db, payload.tvmaze_id, current_user.id)
    if existing:
        raise HTTPException(status_code=409, detail="Series already in watchlist")

    details = await tvmaze_svc.get_show_details(payload.tvmaze_id, redis)
    if not details:
        raise HTTPException(status_code=404, detail="TVMaze show not found")

    series = await crud.create_series(db, payload, details, user_id=current_user.id)
    await db.commit()
    await db.refresh(series)

    async def _ingest():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            await ingest_series(series.tvmaze_id, series.name, bg_db, redis, chroma)
            await bg_db.commit()

    asyncio.create_task(_ingest())
    return series


@router.get("/{series_id}", response_model=SeriesOut)
async def get_series(
    series_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    series = await crud.get_series_by_id(db, series_id, current_user.id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    return series


@router.put("/{series_id}", response_model=SeriesOut)
async def update_series(
    series_id: int,
    payload: SeriesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    series = await crud.get_series_by_id(db, series_id, current_user.id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    updated = await crud.update_series(db, series, payload)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/{series_id}", status_code=204)
async def delete_series(
    series_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    series = await crud.get_series_by_id(db, series_id, current_user.id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    chroma = request.app.state.chroma
    tvmaze_id = series.tvmaze_id

    try:
        from app.services.rag import get_collection, delete_bm25_index
        collection = get_collection(chroma)
        results = collection.get(where={"tvmaze_id": tvmaze_id})
        if results["ids"]:
            collection.delete(ids=results["ids"])
        delete_bm25_index(tvmaze_id)
    except Exception:
        pass

    await crud.delete_series(db, series_id, current_user.id)
    await db.commit()


@router.post("/{series_id}/reindex", status_code=202)
async def reindex_series(
    series_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    series = await crud.get_series_by_id(db, series_id, current_user.id)
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    redis = request.app.state.redis
    chroma = request.app.state.chroma
    series.rag_indexed = False
    await db.commit()

    async def _ingest():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            await ingest_series(series.tvmaze_id, series.name, bg_db, redis, chroma)
            await bg_db.commit()

    asyncio.create_task(_ingest())
    return {"message": f"Re-indexing '{series.name}' in background"}


@router.post("/check-seasons")
async def check_all_seasons(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime, timedelta
    from app.services import tvmaze as tvmaze_svc
    from app.services.crud import get_series_for_season_check

    redis = request.app.state.redis
    now = datetime.utcnow()
    today = now.date()
    soon_window = timedelta(days=7)

    # Only check this user's shows
    all_series = await crud.get_series_list(db, user_id=current_user.id)
    checked = 0
    updated = 0
    shows_with_new = []
    shows_with_upcoming = []

    for series in all_series:
        new_count = await tvmaze_svc.check_season_count(
            series.tvmaze_id, redis, force_refresh=True
        )
        checked += 1
        if new_count > series.total_seasons:
            series.total_seasons = new_count
            series.has_new_season = True
            updated += 1
            shows_with_new.append(series.name)

        next_info = await tvmaze_svc.get_next_episode_info(series.tvmaze_id, redis)
        if next_info and next_info.get("airdate"):
            series.next_ep_season = next_info["season"]
            series.next_ep_number = next_info["number"]
            series.next_ep_airdate = next_info["airdate"]
            try:
                air_date = datetime.strptime(next_info["airdate"], "%Y-%m-%d").date()
                if today <= air_date <= today + soon_window:
                    days_away = (air_date - today).days
                    label = "today" if days_away == 0 else "tomorrow" if days_away == 1 else f"in {days_away} days"
                    shows_with_upcoming.append(
                        f"{series.name} S{next_info['season']:02d}E{next_info['number']:02d} ({label})"
                    )
            except ValueError:
                pass
        elif next_info is None:
            series.next_ep_season = None
            series.next_ep_number = None
            series.next_ep_airdate = None

        series.last_season_check = now

    await db.commit()
    return {
        "checked": checked,
        "updated": updated,
        "shows_with_new": shows_with_new,
        "shows_with_upcoming": shows_with_upcoming,
    }
