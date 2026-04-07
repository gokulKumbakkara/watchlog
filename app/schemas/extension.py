from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class ExtensionPayload(BaseModel):
    show_name: str
    season: int
    episode: int
    source: str
    timestamp: Optional[datetime] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        allowed = {"netflix", "disney", "prime", "hbo", "hotstar", "other"}
        if v.lower() not in allowed:
            return "other"
        return v.lower()

    @field_validator("timestamp", mode="before")
    @classmethod
    def default_timestamp(cls, v):
        return v or datetime.utcnow()


class ExtensionResponse(BaseModel):
    updated: bool
    series_id: Optional[int]
    message: str
