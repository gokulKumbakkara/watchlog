from fastapi import APIRouter
from app.api.v1 import health, series, agent, extension, auth

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(health.router)
router.include_router(series.router)
router.include_router(agent.router)
router.include_router(extension.router)
