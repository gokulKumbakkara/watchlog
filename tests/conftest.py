import asyncio
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Series

TEST_DATABASE_URL = "postgresql+asyncpg://watchlog:watchlog@localhost:5432/watchlog_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db(setup_db) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    from app.db.session import get_db

    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Mock app state
    import unittest.mock as mock
    app.state.redis = mock.AsyncMock()
    app.state.redis.get = mock.AsyncMock(return_value=None)
    app.state.redis.set = mock.AsyncMock(return_value=True)
    app.state.redis.ping = mock.AsyncMock(return_value=True)
    app.state.chroma = mock.MagicMock()
    app.state.chroma.heartbeat = mock.MagicMock(return_value=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seed_series(db: AsyncSession) -> Series:
    series = Series(
        tvmaze_id=82,
        name="Game of Thrones",
        poster_url="https://static.tvmaze.com/uploads/images/medium_portrait/143/357888.jpg",
        network="HBO",
        genre="Drama,Adventure,Fantasy",
        status="Watching",
        current_season=3,
        current_episode=5,
        total_seasons=8,
        total_episodes=73,
        rag_indexed=False,
        added_at=datetime.utcnow(),
    )
    db.add(series)
    await db.commit()
    await db.refresh(series)
    return series
