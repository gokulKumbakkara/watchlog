from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    setup_logging()
    logger.info("WatchLog starting up…")

    # Run pending Alembic migrations on startup
    import subprocess, sys
    result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.error(f"Alembic migration failed: {result.stderr}")
    else:
        logger.info("Alembic migrations applied")

    # Redis
    import redis.asyncio as aioredis
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis connection pool initialised")

    # ChromaDB
    import chromadb
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    app.state.chroma = chroma_client
    logger.info("ChromaDB initialised at %s", settings.CHROMA_PERSIST_DIR)

    # Sentence-transformer embedding model (singleton)
    from sentence_transformers import SentenceTransformer
    app.state.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    logger.info("Embedding model loaded: %s", settings.EMBEDDING_MODEL)

    # Wire scheduler state so the job can access Redis/Chroma
    from app.services import scheduler_state
    scheduler_state.set_redis(app.state.redis)
    scheduler_state.set_chroma(app.state.chroma)

    # Scheduler
    from app.services.scheduler import start_scheduler
    scheduler = start_scheduler()
    app.state.scheduler = scheduler
    logger.info("APScheduler started")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("WatchLog shutting down…")
    app.state.scheduler.shutdown(wait=False)
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("Shutdown complete")
