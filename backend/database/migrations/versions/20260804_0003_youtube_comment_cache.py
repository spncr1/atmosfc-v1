"""Add YouTube comment cache.

Revision ID: 20260804_0003
Revises: 20260804_0002
Create Date: 2026-08-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260804_0003"
down_revision = "20260804_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "youtube_comment_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("raw_comment_count", sa.Integer(), nullable=True),
        sa.Column("analysed_comment_count", sa.Integer(), nullable=True),
        sa.Column("source_video_count", sa.Integer(), nullable=True),
        sa.Column("best_video_url", sa.Text(), nullable=True),
        sa.Column("best_video_title", sa.Text(), nullable=True),
        sa.Column("best_video_channel", sa.String(length=160), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fixture_id"], ["fixtures.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fixture_id", name="uq_youtube_comment_cache_fixture"),
    )
    op.create_index("ix_youtube_comment_cache_checked_at", "youtube_comment_cache", ["checked_at"])
    op.create_index("ix_youtube_comment_cache_status", "youtube_comment_cache", ["status"])


def downgrade() -> None:
    op.drop_index("ix_youtube_comment_cache_status", table_name="youtube_comment_cache")
    op.drop_index("ix_youtube_comment_cache_checked_at", table_name="youtube_comment_cache")
    op.drop_table("youtube_comment_cache")
