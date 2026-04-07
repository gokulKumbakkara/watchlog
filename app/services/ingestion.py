import time
from typing import Optional

from loguru import logger
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import tvmaze as tvmaze_svc
from app.services.rag import get_collection, save_bm25_index
from app.services.search import web_search


async def ingest_series(
    tvmaze_id: int,
    show_name: str,
    db: AsyncSession,
    redis,
    chroma,
) -> None:
    t0 = time.monotonic()
    logger.info(f"Ingestion started: {show_name} (tvmaze_id={tvmaze_id})")

    details = await tvmaze_svc.get_show_details(tvmaze_id, redis)
    episodes = await tvmaze_svc.get_episodes(tvmaze_id, redis)

    if not details:
        logger.warning(f"Ingestion aborted — could not fetch details for tvmaze_id={tvmaze_id}")
        return

    collection = get_collection(chroma)
    documents: list[str] = []
    metadatas: list[dict] = []
    doc_ids: list[str] = []

    # ── Show overview doc ──────────────────────────────────────────────────────
    summary = details.get("summary") or ""
    if summary:
        import re
        summary = re.sub(r"<[^>]+>", "", summary)

    documents.append(summary or f"{show_name} is a TV series.")
    metadatas.append({
        "show_name": show_name,
        "tvmaze_id": tvmaze_id,
        "doc_type": "show_overview",
        "season": 0,
        "episode": 0,
        "episode_title": "Overview",
        "airdate": "",
    })
    doc_ids.append(f"{tvmaze_id}_overview")

    # ── Episode docs ───────────────────────────────────────────────────────────
    for ep in episodes:
        season = ep.get("season", 0)
        episode = ep.get("number", 0)
        ep_title = ep.get("name", f"S{season:02d}E{episode:02d}")
        airdate = ep.get("airdate", "")
        ep_summary = ep.get("summary") or ""

        import re
        ep_summary = re.sub(r"<[^>]+>", "", ep_summary)

        if not ep_summary or len(ep_summary) < 50:
            query = f'"{show_name}" S{season}E{episode} recap what happened'
            ep_summary = await web_search(query, max_results=3)
            logger.info(f"Used DDG fallback for {show_name} S{season:02d}E{episode:02d}")

        doc_text = f"Episode {ep_title}: {ep_summary}"
        doc_id = f"{tvmaze_id}_s{season}_e{episode}"

        documents.append(doc_text)
        metadatas.append({
            "show_name": show_name,
            "tvmaze_id": tvmaze_id,
            "doc_type": "episode_summary",
            "season": season,
            "episode": episode,
            "episode_title": ep_title,
            "airdate": airdate,
        })
        doc_ids.append(doc_id)

    # ── Upsert into ChromaDB ───────────────────────────────────────────────────
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        collection.upsert(
            ids=doc_ids[i:i + batch_size],
            documents=documents[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
        )

    # ── Build BM25 index ───────────────────────────────────────────────────────
    tokenized = [d.lower().split() for d in documents]
    bm25_index = BM25Okapi(tokenized)
    save_bm25_index(tvmaze_id, bm25_index, doc_ids)

    # ── Mark as indexed ────────────────────────────────────────────────────────
    from app.services.crud import get_series_by_tvmaze_id
    from datetime import datetime
    series = await get_series_by_tvmaze_id(db, tvmaze_id)
    if series:
        series.rag_indexed = True
        series.updated_at = datetime.utcnow()
        await db.flush()

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(
        f"Ingestion complete: {show_name} — {len(episodes)} episodes, "
        f"{len(documents)} docs, duration={elapsed}ms"
    )
