import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.db.models import Series


@pytest.mark.asyncio
async def test_list_series_empty(client: AsyncClient):
    resp = await client.get("/api/v1/series")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_series_success(client: AsyncClient):
    mock_details = {
        "id": 82,
        "name": "Game of Thrones",
        "image": {"medium": "https://example.com/got.jpg"},
        "network": {"name": "HBO"},
        "webChannel": None,
        "genres": ["Drama", "Fantasy"],
        "summary": "<p>Epic fantasy.</p>",
        "_embedded": {
            "episodes": [
                {"season": 1, "number": 1, "name": "Winter is Coming", "airdate": "2011-04-17", "summary": ""},
                {"season": 1, "number": 2, "name": "The Kingsroad", "airdate": "2011-04-24", "summary": ""},
            ],
            "nextepisode": None,
        },
    }

    with patch("app.api.v1.series.tvmaze_svc.get_show_details", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_details
        with patch("app.api.v1.series.asyncio.create_task"):
            resp = await client.post("/api/v1/series", json={"tvmaze_id": 82})

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Game of Thrones"
    assert data["tvmaze_id"] == 82
    assert data["network"] == "HBO"


@pytest.mark.asyncio
async def test_update_progress(client: AsyncClient, seed_series: Series):
    resp = await client.put(
        f"/api/v1/series/{seed_series.id}",
        json={"current_season": 4, "current_episode": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_season"] == 4
    assert data["current_episode"] == 2


@pytest.mark.asyncio
async def test_delete_series(client: AsyncClient, seed_series: Series):
    with patch("app.api.v1.series.get_collection") as mock_coll:
        mock_coll.return_value.get.return_value = {"ids": []}
        resp = await client.delete(f"/api/v1/series/{seed_series.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_extension_endpoint_valid_key(client: AsyncClient, seed_series: Series):
    from app.core.config import settings
    resp = await client.post(
        "/api/v1/extension/now-playing",
        json={
            "show_name": "Game of Thrones",
            "season": 4,
            "episode": 1,
            "source": "hbo",
        },
        headers={"X-Extension-Key": settings.EXTENSION_API_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] is True


@pytest.mark.asyncio
async def test_extension_endpoint_invalid_key_returns_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/extension/now-playing",
        json={"show_name": "Test", "season": 1, "episode": 1, "source": "netflix"},
        headers={"X-Extension-Key": "wrong_key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_extension_endpoint_idempotent(client: AsyncClient, seed_series: Series):
    from app.core.config import settings
    # seed_series is at S3E5 — post same values
    resp = await client.post(
        "/api/v1/extension/now-playing",
        json={
            "show_name": "Game of Thrones",
            "season": seed_series.current_season,
            "episode": seed_series.current_episode,
            "source": "hbo",
        },
        headers={"X-Extension-Key": settings.EXTENSION_API_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] is False
