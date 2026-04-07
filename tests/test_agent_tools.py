import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Series


def _make_series(**kwargs) -> Series:
    defaults = dict(
        id=1,
        tvmaze_id=82,
        name="Game of Thrones",
        status="Watching",
        current_season=3,
        current_episode=5,
        total_seasons=8,
        total_episodes=73,
        has_new_season=False,
        rag_indexed=False,
        added_at=datetime.utcnow(),
        genre="Drama,Fantasy",
        last_watched=None,
    )
    defaults.update(kwargs)
    s = Series(**defaults)
    return s


@pytest.mark.asyncio
async def test_get_watchlist_empty(db: AsyncSession):
    from app.agent.tools import inject_dependencies, get_watchlist
    from app.db.session import AsyncSessionLocal

    inject_dependencies(AsyncSessionLocal, MagicMock(), MagicMock(), MagicMock())

    with patch("app.services.crud.get_series_list", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        result = get_watchlist.invoke({})

    assert "No series found" in result


@pytest.mark.asyncio
async def test_update_progress_tool_fuzzy_match(db: AsyncSession):
    from app.agent.tools import inject_dependencies, update_progress
    from app.db.session import AsyncSessionLocal

    series = _make_series()
    inject_dependencies(AsyncSessionLocal, MagicMock(), MagicMock(), MagicMock())

    with patch("app.services.crud.fuzzy_match_series", new_callable=AsyncMock) as mock_fuzzy:
        mock_fuzzy.return_value = series
        with patch.object(db, "commit", new_callable=AsyncMock):
            result = update_progress.invoke({"show_name": "game of thrones", "season": 4, "episode": 1})

    assert "Game of Thrones" in result
    assert "Season 4" in result


@pytest.mark.asyncio
async def test_mark_status_tool():
    from app.agent.tools import inject_dependencies, mark_status
    from app.db.session import AsyncSessionLocal

    series = _make_series()
    inject_dependencies(AsyncSessionLocal, MagicMock(), MagicMock(), MagicMock())

    with patch("app.services.crud.fuzzy_match_series", new_callable=AsyncMock) as mock_fuzzy:
        mock_fuzzy.return_value = series
        result = mark_status.invoke({"show_name": "Game of Thrones", "status": "Completed"})

    assert "Completed" in result


@pytest.mark.asyncio
async def test_check_season_update_tool_with_mock_tvmaze():
    from app.agent.tools import inject_dependencies, check_season_update
    from app.db.session import AsyncSessionLocal

    series = _make_series(total_seasons=7)
    inject_dependencies(AsyncSessionLocal, MagicMock(), MagicMock(), MagicMock())

    with patch("app.services.crud.fuzzy_match_series", new_callable=AsyncMock, return_value=series):
        with patch("app.services.tvmaze.check_season_count", new_callable=AsyncMock, return_value=8):
            result = check_season_update.invoke({"show_name": "Game of Thrones"})

    assert "New season" in result or "8 seasons" in result
