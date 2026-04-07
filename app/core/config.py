from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"
    GROQ_API_KEY: str
    EXTENSION_API_KEY: str = "changeme"

    TVMAZE_BASE_URL: str = "https://api.tvmaze.com"
    TVMAZE_CACHE_TTL: int = 21600
    BM25_CACHE_TTL: int = 3600

    SEASON_CHECK_MONTHS: int = 6

    CHROMA_PERSIST_DIR: str = "./chroma_db"
    BM25_INDEX_DIR: str = "./bm25_indexes"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    AGENT_RATE_LIMIT: str = "20/minute"

    JWT_SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False


settings = Settings()
