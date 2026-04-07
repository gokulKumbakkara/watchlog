from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


class SeriesNotFoundError(Exception):
    def __init__(self, series_id: int | str):
        self.series_id = series_id
        super().__init__(f"Series not found: {series_id}")


class TVMazeError(Exception):
    pass


class RAGNotIndexedError(Exception):
    def __init__(self, show_name: str):
        self.show_name = show_name
        super().__init__(f"Show not yet RAG-indexed: {show_name}")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SeriesNotFoundError)
    async def series_not_found_handler(request: Request, exc: SeriesNotFoundError):
        return JSONResponse(status_code=404, content={"error": "Series not found", "detail": str(exc)})

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.method} {request.url}: {exc}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
