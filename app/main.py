from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.api.v1.router import router

limiter = Limiter(key_func=get_remote_address)


def create_app() -> FastAPI:
    app = FastAPI(
        title="WatchLog",
        description="Personal TV series tracker with LangChain ReAct agent and hybrid RAG search",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.DEBUG,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # API routes
    app.include_router(router)

    # Static frontend
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

    return app


app = create_app()
