"""add users and user_id foreign keys

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Add user_id to series
    op.add_column("series", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_series_user_id", "series", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_series_user_id", "series", ["user_id"])

    # Drop old global unique on tvmaze_id, add per-user unique
    op.drop_index("ix_series_tvmaze_id", table_name="series")
    op.create_unique_constraint("uq_series_user_tvmaze", "series", ["user_id", "tvmaze_id"])

    # Add user_id to conversation_history
    op.add_column("conversation_history", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_conv_user_id", "conversation_history", "users", ["user_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_conv_user_id", "conversation_history", type_="foreignkey")
    op.drop_column("conversation_history", "user_id")

    op.drop_constraint("uq_series_user_tvmaze", "series", type_="unique")
    op.create_index("ix_series_tvmaze_id", "series", ["tvmaze_id"], unique=True)
    op.drop_index("ix_series_user_id", table_name="series")
    op.drop_constraint("fk_series_user_id", "series", type_="foreignkey")
    op.drop_column("series", "user_id")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
