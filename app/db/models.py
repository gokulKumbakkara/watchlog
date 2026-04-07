from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    series: Mapped[list["Series"]] = relationship("Series", back_populates="owner", lazy="noload")

    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_username", "username", unique=True),
    )


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    tvmaze_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    network: Mapped[str | None] = mapped_column(String(100), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Watching", nullable=False)
    current_season: Mapped[int] = mapped_column(Integer, default=1)
    current_episode: Mapped[int] = mapped_column(Integer, default=0)
    total_seasons: Mapped[int] = mapped_column(Integer, default=0)
    total_episodes: Mapped[int] = mapped_column(Integer, default=0)
    has_new_season: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_watched: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_season_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_ep_season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_ep_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_ep_airdate: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extension_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rag_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)

    owner: Mapped["User | None"] = relationship("User", back_populates="series")

    __table_args__ = (
        Index("ix_series_user_id", "user_id"),
        Index("ix_series_status", "status"),
        UniqueConstraint("user_id", "tvmaze_id", name="uq_series_user_tvmaze"),
    )


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_conversation_session_id", "session_id"),
    )
