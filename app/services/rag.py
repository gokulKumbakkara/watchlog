import os
import pickle
from collections import defaultdict
from typing import Optional

import chromadb
import numpy as np
from loguru import logger
from rank_bm25 import BM25Okapi

from app.core.config import settings

COLLECTION_NAME = "series_knowledge"


def get_collection(chroma: chromadb.ClientAPI) -> chromadb.Collection:
    return chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _bm25_index_path(tvmaze_id: int) -> str:
    return os.path.join(settings.BM25_INDEX_DIR, f"{tvmaze_id}.pkl")


def _bm25_docids_path(tvmaze_id: int) -> str:
    return os.path.join(settings.BM25_INDEX_DIR, f"{tvmaze_id}_ids.pkl")


def load_bm25_index(tvmaze_id: int):
    idx_path = _bm25_index_path(tvmaze_id)
    ids_path = _bm25_docids_path(tvmaze_id)
    if not os.path.exists(idx_path) or not os.path.exists(ids_path):
        return None, None
    with open(idx_path, "rb") as f:
        index = pickle.load(f)
    with open(ids_path, "rb") as f:
        doc_ids = pickle.load(f)
    return index, doc_ids


def save_bm25_index(tvmaze_id: int, index: BM25Okapi, doc_ids: list[str]) -> None:
    os.makedirs(settings.BM25_INDEX_DIR, exist_ok=True)
    with open(_bm25_index_path(tvmaze_id), "wb") as f:
        pickle.dump(index, f)
    with open(_bm25_docids_path(tvmaze_id), "wb") as f:
        pickle.dump(doc_ids, f)


def delete_bm25_index(tvmaze_id: int) -> None:
    for path in [_bm25_index_path(tvmaze_id), _bm25_docids_path(tvmaze_id)]:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted BM25 index file: {path}")


def _rrf_merge(
    vector_ids: list[str],
    bm25_ids: list[str],
    k: int = 60,
    top_k: int = 5,
) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for rank, doc_id in enumerate(vector_ids):
        scores[doc_id] += 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(bm25_ids):
        scores[doc_id] += 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]


async def hybrid_search(
    query: str,
    show_name: str,
    tvmaze_id: int,
    chroma: chromadb.ClientAPI,
    season: Optional[int] = None,
    top_k: int = 5,
) -> list[dict]:
    collection = get_collection(chroma)
    fetch_n = top_k * 2

    # ── Vector search ─────────────────────────────────────────────────────────
    where_filter: dict = {"show_name": show_name}
    if season:
        where_filter["season"] = season

    try:
        chroma_results = collection.query(
            query_texts=[query],
            n_results=fetch_n,
            where=where_filter,
        )
        vector_ids: list[str] = chroma_results["ids"][0] if chroma_results["ids"] else []
    except Exception as e:
        logger.warning(f"ChromaDB vector search error for {show_name}: {e}")
        vector_ids = []

    # ── BM25 search ───────────────────────────────────────────────────────────
    bm25_index, doc_ids = load_bm25_index(tvmaze_id)
    bm25_ids: list[str] = []

    if bm25_index is None:
        logger.warning(f"BM25 index not found for tvmaze_id={tvmaze_id}, skipping BM25")
    else:
        tokenized_query = query.lower().split()
        scores = bm25_index.get_scores(tokenized_query)

        if season and doc_ids:
            # Zero out scores for docs not matching the season filter
            for i, doc_id in enumerate(doc_ids):
                parts = doc_id.split("_")
                # id format: {tvmaze_id}_s{season}_e{episode} or {tvmaze_id}_overview
                if f"_s{season}_" not in doc_id and not (season == 0 and "overview" in doc_id):
                    scores[i] = 0.0

        if len(scores) > 0:
            ranked_indices = np.argsort(scores)[::-1][:fetch_n]
            bm25_ids = [doc_ids[i] for i in ranked_indices if scores[i] > 0]

    # ── RRF merge ─────────────────────────────────────────────────────────────
    final_ids = _rrf_merge(vector_ids, bm25_ids, k=60, top_k=top_k)

    if not final_ids:
        return []

    # ── Fetch full documents ──────────────────────────────────────────────────
    try:
        fetched = collection.get(ids=final_ids, include=["documents", "metadatas"])
        results = []
        for doc, meta in zip(fetched["documents"], fetched["metadatas"]):
            results.append({"document": doc, "metadata": meta})
        return results
    except Exception as e:
        logger.error(f"ChromaDB get failed for ids={final_ids}: {e}")
        return []
