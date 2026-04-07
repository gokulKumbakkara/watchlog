"""initial

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tvmaze_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("poster_url", sa.String(500), nullable=True),
        sa.Column("network", sa.String(100), nullable=True),
        sa.Column("genre", sa.String(200), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="Watching"),
        sa.Column("current_season", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_episode", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_seasons", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_episodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_new_season", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_watched", sa.DateTime(), nullable=True),
        sa.Column("last_season_check", sa.DateTime(), nullable=True),
        sa.Column("next_ep_season", sa.Integer(), nullable=True),
        sa.Column("next_ep_number", sa.Integer(), nullable=True),
        sa.Column("next_ep_airdate", sa.String(50), nullable=True),
        sa.Column("extension_source", sa.String(50), nullable=True),
        sa.Column("rag_indexed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_series_tvmaze_id", "series", ["tvmaze_id"], unique=True)
    op.create_index("ix_series_status", "series", ["status"])

    op.create_table(
        "conversation_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_session_id", "conversation_history", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_conversation_session_id", table_name="conversation_history")
    op.drop_table("conversation_history")
    op.drop_index("ix_series_status", table_name="series")
    op.drop_index("ix_series_tvmaze_id", table_name="series")
    op.drop_table("series")
