from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SeriesCreate(BaseModel):
    tvmaze_id: int
    status: str = "Watching"
    notes: Optional[str] = None


class SeriesUpdate(BaseModel):
    status: Optional[str] = None
    current_season: Optional[int] = None
    current_episode: Optional[int] = None
    notes: Optional[str] = None
    last_watched: Optional[datetime] = None


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tvmaze_id: int
    name: str
    poster_url: Optional[str]
    network: Optional[str]
    genre: Optional[str]
    status: str
    current_season: int
    current_episode: int
    total_seasons: int
    total_episodes: int
    has_new_season: bool
    notes: Optional[str]
    last_watched: Optional[datetime]
    last_season_check: Optional[datetime]
    next_ep_season: Optional[int]
    next_ep_number: Optional[int]
    next_ep_airdate: Optional[str]
    extension_source: Optional[str]
    rag_indexed: bool
    added_at: datetime
    updated_at: Optional[datetime]


class TVMazeSearchResult(BaseModel):
    tvmaze_id: int
    name: str
    poster_url: Optional[str]
    network: Optional[str]
    genre: Optional[str]
    status: Optional[str]
    summary: Optional[str]
    score: float = 0.0
