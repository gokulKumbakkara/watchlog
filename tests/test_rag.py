import os
import pickle
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag import (
    get_collection,
    save_bm25_index,
    load_bm25_index,
    delete_bm25_index,
    hybrid_search,
    _rrf_merge,
)


@pytest.fixture
def tmp_bm25_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.rag.settings.BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr("app.core.config.settings.BM25_INDEX_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_chroma():
    chroma = MagicMock()
    collection = MagicMock()
    chroma.get_or_create_collection.return_value = collection
    return chroma, collection


@pytest.mark.asyncio
async def test_ingest_creates_chroma_docs(tmp_bm25_dir, mock_chroma):
    chroma, collection = mock_chroma
    collection.upsert = MagicMock()

    mock_details = {
        "id": 82,
        "name": "Game of Thrones",
        "summary": "<p>Epic fantasy series.</p>",
        "_embedded": {
            "episodes": [
                {"season": 1, "number": 1, "name": "Winter is Coming",
                 "airdate": "2011-04-17", "summary": "The Stark family is introduced."},
            ],
            "nextepisode": None,
        },
    }
    mock_episodes = [
        {"season": 1, "number": 1, "name": "Winter is Coming",
         "airdate": "2011-04-17", "summary": "The Stark family is introduced."},
    ]

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()

    with patch("app.services.ingestion.tvmaze_svc.get_show_details", new_callable=AsyncMock, return_value=mock_details):
        with patch("app.services.ingestion.tvmaze_svc.get_episodes", new_callable=AsyncMock, return_value=mock_episodes):
            with patch("app.services.ingestion.get_series_by_tvmaze_id", new_callable=AsyncMock, return_value=None):
                from app.services.ingestion import ingest_series
                await ingest_series(82, "Game of Thrones", mock_db, MagicMock(), chroma)

    assert collection.upsert.called
    call_kwargs = collection.upsert.call_args_list[0][1]
    assert "82_overview" in call_kwargs["ids"]


@pytest.mark.asyncio
async def test_bm25_index_built_and_persisted(tmp_bm25_dir):
    from rank_bm25 import BM25Okapi
    docs = ["winter is coming stark family", "red wedding rains of castamere"]
    tokenized = [d.split() for d in docs]
    index = BM25Okapi(tokenized)
    doc_ids = ["doc_0", "doc_1"]

    save_bm25_index(82, index, doc_ids)

    loaded_index, loaded_ids = load_bm25_index(82)
    assert loaded_index is not None
    assert loaded_ids == doc_ids
    scores = loaded_index.get_scores(["winter"])
    assert scores[0] > scores[1]


@pytest.mark.asyncio
async def test_hybrid_search_returns_results(tmp_bm25_dir, mock_chroma):
    from rank_bm25 import BM25Okapi
    chroma, collection = mock_chroma

    docs = ["Episode Winter is Coming: The Starks face a threat."]
    doc_ids = ["82_s1_e1"]
    tokenized = [d.lower().split() for d in docs]
    index = BM25Okapi(tokenized)
    save_bm25_index(82, index, doc_ids)

    collection.query.return_value = {
        "ids": [["82_s1_e1"]],
        "documents": [["Episode Winter is Coming: The Starks face a threat."]],
        "metadatas": [[{"show_name": "Game of Thrones", "season": 1, "episode": 1}]],
    }
    collection.get.return_value = {
        "ids": ["82_s1_e1"],
        "documents": ["Episode Winter is Coming: The Starks face a threat."],
        "metadatas": [{"show_name": "Game of Thrones", "season": 1, "episode": 1}],
    }

    results = await hybrid_search(
        query="winter threat stark",
        show_name="Game of Thrones",
        tvmaze_id=82,
        chroma=chroma,
        top_k=5,
    )
    assert len(results) > 0
    assert "Starks" in results[0]["document"]


def test_rrf_merges_both_lists():
    vector_ids = ["doc_a", "doc_b", "doc_c"]
    bm25_ids = ["doc_c", "doc_a", "doc_d"]
    merged = _rrf_merge(vector_ids, bm25_ids, k=60, top_k=3)

    # doc_a and doc_c appear in both lists — should rank high
    assert "doc_a" in merged
    assert "doc_c" in merged
    assert len(merged) == 3
