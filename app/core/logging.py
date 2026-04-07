import sys
from loguru import logger
from app.core.config import settings


def setup_logging() -> None:
    logger.remove()

    logger.add(
        sys.stderr,
        format="{time:ISO8601} | {level} | {name} | {message}",
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    logger.add(
        "logs/watchlog.json",
        format="{time:ISO8601} | {level} | {name} | {message}",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        serialize=True,
    )
