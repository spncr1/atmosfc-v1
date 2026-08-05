"""Add analysis cache.

Revision ID: 20260805_0005
Revises: 20260804_0004
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260805_0005"
down_revision = "20260804_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), server_default=sa.text("'complete'"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_video_count", sa.Integer(), nullable=True),
        sa.Column("total_comments", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["fixture_id"], ["fixtures.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fixture_id", name="uq_analysis_cache_fixture"),
    )
    op.create_index("ix_analysis_cache_status", "analysis_cache", ["status"])
    op.create_index("ix_analysis_cache_checked_at", "analysis_cache", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_analysis_cache_checked_at", table_name="analysis_cache")
    op.drop_index("ix_analysis_cache_status", table_name="analysis_cache")
    op.drop_table("analysis_cache")
