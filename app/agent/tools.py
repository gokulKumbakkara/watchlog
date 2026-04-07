import asyncio
import contextvars
import time
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool
from loguru import logger


# ── Dependency injection holders ───────────────────────────────────────────────
_db_factory = None
_redis = None
_chroma = None
_groq_llm = None

# Per-request user context (safe for concurrent async requests)
_current_user_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_user_id", default=None
)


def inject_dependencies(db_factory, redis, chroma, groq_llm):
    global _db_factory, _redis, _chroma, _groq_llm
    _db_factory = db_factory
    _redis = redis
    _chroma = chroma
    _groq_llm = groq_llm


def set_user_context(user_id: int):
    _current_user_id.set(user_id)


def _uid() -> int:
    uid = _current_user_id.get()
    if uid is None:
        raise RuntimeError("No user_id set in context — call set_user_context() before running agent tools")
    return uid


# ── Tool implementations ───────────────────────────────────────────────────────

@tool
async def search_and_add(show_name: str) -> str:
    """Search TVMaze for a TV show and add it to the watchlist."""
    t0 = time.monotonic()
    logger.info(f"Tool: search_and_add called with show_name={show_name!r}")

    from app.services import tvmaze as tvmaze_svc
    from app.services.crud import create_series, get_series_by_tvmaze_id
    from app.schemas.series import SeriesCreate
    from app.services.ingestion import ingest_series

    results = await tvmaze_svc.search_shows(show_name, _redis)
    if not results:
        return f"No results found for '{show_name}' on TVMaze."

    best = results[0]
    show = best.get("show", {})
    tvmaze_id = show.get("id")
    name = show.get("name", show_name)

    async with _db_factory() as db:
        existing = await get_series_by_tvmaze_id(db, tvmaze_id, _uid())
        if existing:
            return f"'{name}' is already in your watchlist."

        details = await tvmaze_svc.get_show_details(tvmaze_id, _redis)
        if not details:
            return f"Could not fetch details for '{name}'."

        payload = SeriesCreate(tvmaze_id=tvmaze_id)
        series = await create_series(db, payload, details, user_id=_uid())
        await db.commit()

    # Background ingestion in a separate session
    async def _ingest():
        async with _db_factory() as bg_db:
            await ingest_series(tvmaze_id, name, bg_db, _redis, _chroma)
            await bg_db.commit()

    asyncio.create_task(_ingest())

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: search_and_add completed in {elapsed}ms")
    return (
        f"Added '{name}' to your watchlist. "
        f"It has {series.total_seasons} seasons and {series.total_episodes} episodes. "
        "Episode summaries are being indexed in the background."
    )


@tool
async def update_progress(show_name: str, season: int, episode: int) -> str:
    """Update your current watching progress for a TV show."""
    t0 = time.monotonic()
    logger.info(f"Tool: update_progress show={show_name!r} S{season}E{episode}")

    from app.services.crud import fuzzy_match_series

    async with _db_factory() as db:
        series = await fuzzy_match_series(db, show_name, _uid())
        if not series:
            return f"Could not find '{show_name}' in your watchlist."

        series.current_season = season
        series.current_episode = episode
        series.last_watched = datetime.utcnow()
        series.has_new_season = False
        series.updated_at = datetime.utcnow()
        await db.commit()

        progress = ""
        if series.total_episodes > 0:
            pct = round((episode / series.total_episodes) * 100, 1)
            progress = f" ({pct}% through the series)"

        name = series.name

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: update_progress completed in {elapsed}ms")
    return f"Updated '{name}' progress to Season {season}, Episode {episode}{progress}."


@tool
async def get_watchlist(status: str = "") -> str:
    """Get your TV series watchlist, optionally filtered by status (Watching/Completed/On Hold/Dropped/Plan to Watch)."""
    t0 = time.monotonic()
    logger.info(f"Tool: get_watchlist status={status!r}")

    from app.services.crud import get_series_list

    filter_status = status if status else None

    async with _db_factory() as db:
        series_list = await get_series_list(db, user_id=_uid(), status=filter_status)

    if not series_list:
        label = f" with status '{status}'" if status else ""
        return f"No series found{label} in your watchlist."

    lines = []
    for s in series_list:
        new_flag = " [NEW SEASON AVAILABLE]" if s.has_new_season else ""
        last = s.last_watched.strftime("%Y-%m-%d") if s.last_watched else "never"
        lines.append(
            f"- {s.name}{new_flag}\n"
            f"  Status: {s.status} | Progress: S{s.current_season:02d}E{s.current_episode:02d} "
            f"| Last watched: {last}"
        )

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: get_watchlist returned {len(series_list)} shows in {elapsed}ms")
    header = f"Your watchlist ({len(series_list)} shows):\n" if not status else f"Watchlist ({status}):\n"
    return header + "\n".join(lines)


@tool
async def check_season_update(show_name: str) -> str:
    """Check if a specific TV show has a new season available."""
    t0 = time.monotonic()
    logger.info(f"Tool: check_season_update show={show_name!r}")

    from app.services.crud import fuzzy_match_series
    from app.services import tvmaze as tvmaze_svc
    from app.services.search import web_search

    async with _db_factory() as db:
        series = await fuzzy_match_series(db, show_name, _uid())
        if not series:
            return f"Could not find '{show_name}' in your watchlist."

        new_count = await tvmaze_svc.check_season_count(
            series.tvmaze_id, _redis, force_refresh=True
        )

        # Build next-episode info string if available
        next_info = ""
        if series.next_ep_season and series.next_ep_airdate:
            today = datetime.utcnow().date()
            air_date = series.next_ep_airdate
            # air_date may be a date object or string
            if hasattr(air_date, 'date'):
                air_date_obj = air_date.date()
            else:
                try:
                    air_date_obj = datetime.strptime(str(air_date), "%Y-%m-%d").date()
                except Exception:
                    air_date_obj = None

            if air_date_obj and air_date_obj > today:
                status_note = f"(NOT YET RELEASED — airs in the future on {air_date})"
            elif air_date_obj and air_date_obj == today:
                status_note = f"(AIRING TODAY on {air_date})"
            else:
                status_note = f"(already aired on {air_date})"

            next_info = (
                f" Next episode: S{series.next_ep_season:02d}E{series.next_ep_number:02d} "
                f"{status_note}."
            )

        if new_count > series.total_seasons:
            series.total_seasons = new_count
            series.has_new_season = True
            result_msg = (
                f"New season confirmed! '{series.name}' now has {new_count} seasons "
                f"(you have watched up to season {series.current_season}).{next_info}"
            )
        elif new_count == 0:
            query = f"{series.name} new season release date {datetime.utcnow().year}"
            snippet = await web_search(query)
            logger.warning(f"TVMaze no data for {series.name}, used DDG fallback")
            result_msg = f"TVMaze had no season data for '{series.name}'. Web search result:\n{snippet[:500]}"
        else:
            result_msg = (
                f"'{series.name}' currently has {new_count} seasons total. "
                f"You are at S{series.current_season:02d}E{series.current_episode:02d}.{next_info}"
            )

        series.last_season_check = datetime.utcnow()
        await db.commit()

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: check_season_update completed in {elapsed}ms")
    return result_msg


@tool
async def check_all_seasons(query: str = "") -> str:
    """Check all actively watched and on-hold shows for new seasons."""
    t0 = time.monotonic()
    logger.info("Tool: check_all_seasons called")

    from app.services.crud import get_series_for_season_check
    from app.services import tvmaze as tvmaze_svc
    from app.services.search import web_search

    cutoff = timedelta(days=180)
    now = datetime.utcnow()

    today = now.date()
    soon_window = timedelta(days=7)

    async with _db_factory() as db:
        all_series = await get_series_for_season_check(db)
        due = [
            s for s in all_series
            if s.last_season_check is None or (now - s.last_season_check) > cutoff
        ]

        checked = 0
        updated = 0
        new_season_shows = []
        upcoming_shows = []

        for series in due:
            try:
                new_count = await tvmaze_svc.check_season_count(
                    series.tvmaze_id, _redis, force_refresh=True
                )
                checked += 1

                if new_count > series.total_seasons:
                    series.total_seasons = new_count
                    series.has_new_season = True
                    updated += 1
                    new_season_shows.append(series.name)
                elif new_count == 0:
                    query_str = f"{series.name} new season {now.year}"
                    await web_search(query_str)
                    logger.warning(f"DDG fallback triggered for {series.name}")

                # Refresh next-episode info
                next_info = await tvmaze_svc.get_next_episode_info(series.tvmaze_id, _redis)
                if next_info and next_info.get("airdate"):
                    series.next_ep_season = next_info["season"]
                    series.next_ep_number = next_info["number"]
                    series.next_ep_airdate = next_info["airdate"]
                    try:
                        air_date = datetime.strptime(next_info["airdate"], "%Y-%m-%d").date()
                        if today <= air_date <= today + soon_window:
                            days_away = (air_date - today).days
                            label = "today" if days_away == 0 else "tomorrow" if days_away == 1 else f"in {days_away} days"
                            upcoming_shows.append(
                                f"{series.name} S{next_info['season']:02d}E{next_info['number']:02d} ({label})"
                            )
                    except ValueError:
                        pass

                series.last_season_check = now
            except Exception as e:
                logger.error(f"check_all_seasons error for {series.name}: {e}")
                series.last_season_check = now

        await db.commit()

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: check_all_seasons: {checked} checked, {updated} updated in {elapsed}ms")

    summary = f"Checked {checked} shows. {updated} with new seasons."
    if new_season_shows:
        summary += f"\nNew seasons: {', '.join(new_season_shows)}"
    if upcoming_shows:
        summary += f"\nEpisodes airing soon: {', '.join(upcoming_shows)}"
    if not new_season_shows and not upcoming_shows:
        summary += "\nNo new seasons or upcoming episodes found."
    return summary


@tool
async def search_series_knowledge(query: str, show_name: str = "", season: int = 0) -> str:
    """Search episode summaries and plot details for a specific show. Requires show_name (e.g. 'The Boys') and a query. Always cites episodes (e.g. S02E04)."""
    t0 = time.monotonic()
    logger.info(f"Tool: search_series_knowledge query={query!r} show={show_name!r} season={season}")

    if not show_name:
        return "Please specify which show you want to know about (e.g. show_name='The Boys')."

    from app.services.crud import fuzzy_match_series
    from app.services.rag import hybrid_search
    from app.services.ingestion import ingest_series
    from langchain_core.messages import HumanMessage

    async with _db_factory() as db:
        series = await fuzzy_match_series(db, show_name, _uid())
        if not series:
            return f"Could not find '{show_name}' in your watchlist."

        if not series.rag_indexed:
            await ingest_series(series.tvmaze_id, series.name, db, _redis, _chroma)
            await db.commit()

        season_filter = season if season > 0 else None
        chunks = await hybrid_search(
            query=query,
            show_name=series.name,
            tvmaze_id=series.tvmaze_id,
            chroma=_chroma,
            season=season_filter,
            top_k=5,
        )

    if not chunks and not series.notes:
        return f"No episode information found for '{show_name}' matching your query."

    context_parts = []
    for c in chunks:
        meta = c["metadata"]
        s_num = meta.get("season", 0)
        e_num = meta.get("episode", 0)
        label = f"S{s_num:02d}E{e_num:02d}" if s_num > 0 else "Overview"
        context_parts.append(f"[{label}] {c['document']}")

    episode_context = "\n\n".join(context_parts) if context_parts else "(no episode summaries matched)"

    notes_section = ""
    note_entries = _parse_notes(series.notes)
    if note_entries:
        formatted = _format_notes_for_agent(series.name, note_entries)
        notes_section = (
            f"\n\n2) USER'S PERSONAL NOTES (high-priority — written by the user):\n{formatted}"
        )

    sources_label = "two sources of information" if notes_section else "episode summaries"
    prompt = (
        f"You have {sources_label} about '{show_name}'.\n\n"
        f"1) EPISODE SUMMARIES (from TVMaze):\n{episode_context}"
        f"{notes_section}\n\n"
        f"Question: {query}\n\n"
        "Answer using all available sources. When referencing episode events, cite the episode (e.g. S02E04). "
        "When the answer comes from user notes, say 'According to your notes: ...'."
    )
    response = await _groq_llm.ainvoke([HumanMessage(content=prompt)])
    answer = response.content if hasattr(response, "content") else str(response)

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: search_series_knowledge completed in {elapsed}ms")
    return answer


@tool
async def recommend(mood: str = "") -> str:
    """Get a personalized show recommendation based on your watchlist and optional mood."""
    t0 = time.monotonic()
    logger.info(f"Tool: recommend mood={mood!r}")

    from app.services.crud import get_series_list
    from langchain_core.messages import HumanMessage

    async with _db_factory() as db:
        series_list = await get_series_list(db, user_id=_uid())

    if not series_list:
        return "Your watchlist is empty. Add some shows first!"

    context_lines = [
        f"- {s.name} | Genre: {s.genre or 'Unknown'} | Status: {s.status}"
        for s in series_list
    ]
    context = "\n".join(context_lines)

    mood_clause = f" The user is in the mood for something {mood}." if mood else ""
    prompt = (
        f"Based on this watchlist:\n{context}\n\n"
        f"Recommend the single best next show to watch and explain why.{mood_clause} "
        "Be concise and specific."
    )
    response = await _groq_llm.ainvoke([HumanMessage(content=prompt)])
    answer = response.content if hasattr(response, "content") else str(response)

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: recommend completed in {elapsed}ms")
    return answer


@tool
async def mark_status(show_name: str, status: str) -> str:
    """Mark a TV show with a new status: Watching, Completed, On Hold, Dropped, or Plan to Watch."""
    t0 = time.monotonic()
    logger.info(f"Tool: mark_status show={show_name!r} status={status!r}")

    valid = {"Watching", "Completed", "On Hold", "Dropped", "Plan to Watch", "Waiting for Next Season"}
    if status not in valid:
        return f"Invalid status '{status}'. Choose from: {', '.join(sorted(valid))}"

    from app.services.crud import fuzzy_match_series

    async with _db_factory() as db:
        series = await fuzzy_match_series(db, show_name, _uid())
        if not series:
            return f"Could not find '{show_name}' in your watchlist."

        old_status = series.status
        series.status = status
        series.updated_at = datetime.utcnow()
        await db.commit()
        name = series.name

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: mark_status completed in {elapsed}ms")
    return f"Updated '{name}' status from '{old_status}' to '{status}'."


@tool
async def remove_series(show_name: str) -> str:
    """Remove a TV show from your watchlist, including all indexed data."""
    t0 = time.monotonic()
    logger.info(f"Tool: remove_series show={show_name!r}")

    from app.services.crud import fuzzy_match_series
    from app.services.rag import get_collection, delete_bm25_index

    async with _db_factory() as db:
        series = await fuzzy_match_series(db, show_name, _uid())
        if not series:
            return f"Could not find '{show_name}' in your watchlist."

        name = series.name
        tvmaze_id = series.tvmaze_id

        try:
            collection = get_collection(_chroma)
            results = collection.get(where={"tvmaze_id": tvmaze_id})
            if results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} ChromaDB docs for {name}")
        except Exception as e:
            logger.warning(f"ChromaDB delete failed for {name}: {e}")

        delete_bm25_index(tvmaze_id)
        await db.delete(series)
        await db.commit()

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: remove_series completed in {elapsed}ms")
    return f"Removed '{name}' from your watchlist and deleted all associated data."


def _parse_notes(raw: Optional[str]) -> list:
    """Parse notes JSON or legacy plain text into list of {season, episode, content}."""
    if not raw:
        return []
    try:
        import json
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        return [{"season": 0, "episode": 0, "content": raw}]
    except Exception:
        return [{"season": 0, "episode": 0, "content": raw}] if raw.strip() else []


def _format_notes_for_agent(name: str, entries: list) -> str:
    """Turn structured note entries into readable text for the agent."""
    if not entries:
        return f"No notes saved for '{name}' yet."
    lines = [f"Notes for '{name}':"]
    general = [e for e in entries if e.get("season", 0) == 0 and e.get("episode", 0) == 0]
    if general:
        lines.append(f"  General: {general[0]['content']}")
    for season in sorted({e["season"] for e in entries if e.get("season", 0) > 0}):
        season_note = next((e for e in entries if e["season"] == season and e.get("episode", 0) == 0), None)
        if season_note:
            lines.append(f"  Season {season}: {season_note['content']}")
        ep_notes = [e for e in entries if e["season"] == season and e.get("episode", 0) > 0]
        for ep in sorted(ep_notes, key=lambda x: x["episode"]):
            lines.append(f"  S{season:02d}E{ep['episode']:02d}: {ep['content']}")
    return "\n".join(lines)


@tool
async def manage_notes(show_name: str, action: str = "get", note: str = "", season: int = 0, episode: int = 0) -> str:
    """Read or update personal notes for a TV show.
    action='get' — returns all notes.
    action='set' — sets a note for a specific season/episode (season=0,episode=0 = general).
    action='append' — appends text to an existing note entry.
    season/episode default to 0 (general show note).
    """
    t0 = time.monotonic()
    logger.info(f"Tool: manage_notes show={show_name!r} action={action!r} S{season}E{episode}")

    import json
    from app.services.crud import fuzzy_match_series

    async with _db_factory() as db:
        series = await fuzzy_match_series(db, show_name, _uid())
        if not series:
            return f"Could not find '{show_name}' in your watchlist."

        name = series.name
        entries = _parse_notes(series.notes)

        if action == "get":
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.info(f"Tool: manage_notes get completed in {elapsed}ms")
            return _format_notes_for_agent(name, entries)

        elif action in ("set", "append"):
            if not note:
                return "Please provide the note text."
            idx = next((i for i, e in enumerate(entries)
                        if e.get("season", 0) == season and e.get("episode", 0) == episode), None)
            if action == "set":
                new_content = note.strip()
            else:
                existing = entries[idx]["content"] if idx is not None else ""
                new_content = f"{existing}\n{note.strip()}".strip()

            if idx is not None:
                entries[idx]["content"] = new_content
            else:
                entries.append({"season": season, "episode": episode, "content": new_content})

            series.notes = json.dumps(entries)
            series.updated_at = datetime.utcnow()
            await db.commit()

            label = "General" if season == 0 else f"S{season:02d}E{episode:02d}" if episode > 0 else f"Season {season}"
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.info(f"Tool: manage_notes {action} completed in {elapsed}ms")
            return f"Note saved for '{name}' [{label}]."

        else:
            return f"Unknown action '{action}'. Use 'get', 'set', or 'append'."


@tool
async def web_search_fallback(query: str) -> str:
    """Internal tool: search the web for TV show information when TVMaze has no data."""
    t0 = time.monotonic()
    logger.info(f"Tool: web_search_fallback query={query!r}")

    from app.services.search import web_search
    result = await web_search(query)

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(f"Tool: web_search_fallback completed in {elapsed}ms")
    return result


ALL_TOOLS = [
    search_and_add,
    update_progress,
    get_watchlist,
    check_season_update,
    check_all_seasons,
    search_series_knowledge,
    manage_notes,
    recommend,
    mark_status,
    remove_series,
    web_search_fallback,
]
