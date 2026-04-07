from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationHistory, Series
from app.schemas.series import SeriesCreate, SeriesUpdate


# ── Series ────────────────────────────────────────────────────────────────────

async def get_series_list(db: AsyncSession, user_id: int, status: Optional[str] = None) -> list[Series]:
    stmt = select(Series).where(Series.user_id == user_id)
    if status:
        stmt = stmt.where(Series.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_series_by_id(db: AsyncSession, series_id: int, user_id: int) -> Optional[Series]:
    result = await db.execute(
        select(Series).where(Series.id == series_id, Series.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_series_by_tvmaze_id(db: AsyncSession, tvmaze_id: int, user_id: int) -> Optional[Series]:
    result = await db.execute(
        select(Series).where(Series.tvmaze_id == tvmaze_id, Series.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_series(db: AsyncSession, payload: SeriesCreate, details: dict, user_id: int) -> Series:
    embedded = details.get("_embedded", {})
    episodes = embedded.get("episodes", [])
    total_seasons = max((e.get("season", 0) for e in episodes), default=0)
    total_episodes = len(episodes)

    network = None
    if details.get("network"):
        network = details["network"].get("name")
    elif details.get("webChannel"):
        network = details["webChannel"].get("name")

    genres = details.get("genres", [])

    poster_url = None
    if details.get("image"):
        poster_url = details["image"].get("medium") or details["image"].get("original")

    next_ep = embedded.get("nextepisode", {}) or {}

    series = Series(
        user_id=user_id,
        tvmaze_id=details["id"],
        name=details["name"],
        poster_url=poster_url,
        network=network,
        genre=",".join(genres) if genres else None,
        status=payload.status,
        current_season=1,
        current_episode=0,
        total_seasons=total_seasons,
        total_episodes=total_episodes,
        notes=payload.notes,
        next_ep_season=next_ep.get("season"),
        next_ep_number=next_ep.get("number"),
        next_ep_airdate=next_ep.get("airdate"),
    )
    db.add(series)
    await db.flush()
    await db.refresh(series)
    return series


async def update_series(db: AsyncSession, series: Series, payload: SeriesUpdate) -> Series:
    for field, value in payload.model_dump(exclude_none=True).items():
        # Strip timezone so asyncpg doesn't choke on TIMESTAMP WITHOUT TIME ZONE
        if isinstance(value, datetime) and value.tzinfo is not None:
            value = value.replace(tzinfo=None)
        setattr(series, field, value)
    series.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(series)
    return series


async def delete_series(db: AsyncSession, series_id: int, user_id: int) -> bool:
    result = await db.execute(
        select(Series).where(Series.id == series_id, Series.user_id == user_id)
    )
    series = result.scalar_one_or_none()
    if not series:
        return False
    await db.delete(series)
    await db.flush()
    return True


async def get_series_for_season_check(db: AsyncSession) -> list[Series]:
    stmt = select(Series).where(Series.status.in_(["Watching", "On Hold", "Waiting for Next Season"]))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def fuzzy_match_series(db: AsyncSession, show_name: str, user_id: int) -> Optional[Series]:
    """Case-insensitive substring match within a user's watchlist."""
    result = await db.execute(select(Series).where(Series.user_id == user_id))
    all_series = list(result.scalars().all())
    name_lower = show_name.lower()

    for s in all_series:
        if s.name.lower() == name_lower:
            return s

    candidates = [s for s in all_series if name_lower in s.name.lower() or s.name.lower() in name_lower]
    if candidates:
        return min(candidates, key=lambda s: len(s.name))

    tokens = name_lower.split()
    scored = []
    for s in all_series:
        s_lower = s.name.lower()
        score = sum(1 for t in tokens if t in s_lower)
        if score > 0:
            scored.append((score, s))
    if scored:
        return max(scored, key=lambda x: x[0])[1]

    return None


# ── ConversationHistory ───────────────────────────────────────────────────────

async def save_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    user_id: Optional[int] = None,
    tool_calls: Optional[list] = None,
) -> ConversationHistory:
    msg = ConversationHistory(
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    db.add(msg)
    await db.flush()
    return msg


async def get_recent_messages(
    db: AsyncSession, session_id: str, limit: int = 10
) -> list[ConversationHistory]:
    stmt = (
        select(ConversationHistory)
        .where(ConversationHistory.session_id == session_id)
        .order_by(ConversationHistory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())
    return list(reversed(messages))
