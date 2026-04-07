from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    redis = request.app.state.redis
    chroma = request.app.state.chroma

    # DB check
    db_ok = False
    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Redis check
    redis_ok = False
    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        pass

    # ChromaDB check
    chroma_ok = False
    try:
        chroma.heartbeat()
        chroma_ok = True
    except Exception:
        pass

    status = "ok" if all([db_ok, redis_ok, chroma_ok]) else "degraded"

    return JSONResponse(
        content={
            "status": status,
            "db": db_ok,
            "redis": redis_ok,
            "chroma": chroma_ok,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
